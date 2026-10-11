"""Cleaner and answer-key parser for GATE papers.

Key design decisions per user requirements:
- qtype is detected from the answer key (one letter = MCQ, multiple = MSQ, numeric = NAT)
- marks are derived from section headers, NOT from option count
- Handles MTA (marks-to-all), multiple-correct, NAT ranges
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from app.core.logging import get_logger
from app.ingestion.pdf_parser import parse_section_headers

logger = get_logger(__name__)


@dataclass
class AnswerKeyEntry:
    """A single entry from the official GATE answer key."""

    question_no: int
    raw_answer: str  # The raw string from the key
    qtype: str       # "MCQ" | "MSQ" | "NAT" — derived from answer format
    answer: dict[str, Any]  # Structured answer for DB storage
    is_mta: bool = False  # Marks to all


@dataclass
class CleanedQuestion:
    """A fully cleaned and structured question ready for DB insertion."""

    question_no: int
    text: str
    options: dict[str, str] | None
    qtype: str       # "MCQ" | "MSQ" | "NAT"
    marks: int        # 1 or 2
    answer: dict[str, Any]
    has_figure: bool
    is_mta: bool
    text_hash: str    # SHA-256 of normalised text
    confidence: float
    parse_status: str  # "parsed" | "review_needed"


# ── Answer key patterns ─────────────────────────────────────────────────────

# Matches question number and answer: "1  A" or "1\tA" or "1. A"
_AK_LINE_RE = re.compile(
    r"^\s*(\d+)\s*[.):\t\s]+(.+)$",
    re.MULTILINE,
)

# Single uppercase letter (MCQ)
_SINGLE_LETTER_RE = re.compile(r"^([A-D])$", re.IGNORECASE)

# Multiple letters, possibly separated by commas/semicolons/spaces (MSQ)
_MULTI_LETTER_RE = re.compile(r"^([A-D])\s*[,;\s]+([A-D](?:\s*[,;\s]+[A-D])*)$", re.IGNORECASE)

# Marks to All
_MTA_RE = re.compile(r"marks?\s*to\s*all|MTA", re.IGNORECASE)

# NAT: numeric answer, possibly a range "4.5 to 4.7" or single value
_NAT_RANGE_RE = re.compile(
    r"(-?\d+\.?\d*)\s*(?:to|[-–—])\s*(-?\d+\.?\d*)",
    re.IGNORECASE,
)
_NAT_SINGLE_RE = re.compile(r"^(-?\d+\.?\d*)$")


class AnswerKeyParser:
    """Parses GATE official answer key PDFs.

    Determines question type from the answer format:
    - Single letter → MCQ
    - Multiple letters → MSQ
    - Numeric value or range → NAT
    - "Marks to All" → MTA flag
    """

    def parse_answer_key(self, pdf_path: Path) -> list[AnswerKeyEntry]:
        """Parse an answer key PDF into structured entries.

        Args:
            pdf_path: Path to the answer key PDF.

        Returns:
            List of AnswerKeyEntry objects.
        """
        text = self._extract_text(pdf_path)
        entries: list[AnswerKeyEntry] = []

        for match in _AK_LINE_RE.finditer(text):
            q_no = int(match.group(1))
            raw_answer = match.group(2).strip()

            entry = self._parse_single_answer(q_no, raw_answer)
            if entry:
                entries.append(entry)

        logger.info("answer_key_parsed", file=str(pdf_path), entries=len(entries))
        return entries

    def _extract_text(self, pdf_path: Path) -> str:
        """Extract full text from a PDF."""
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        return text

    def _parse_single_answer(self, q_no: int, raw: str) -> AnswerKeyEntry | None:
        """Parse a single answer key entry and determine qtype.

        Decision logic (from answer key, not option count):
        - "Marks to All" / "MTA" → MCQ with mta=True
        - Single letter A-D → MCQ
        - Multiple letters A-D → MSQ
        - Numeric value or range → NAT
        """
        # Check MTA first
        if _MTA_RE.search(raw):
            return AnswerKeyEntry(
                question_no=q_no,
                raw_answer=raw,
                qtype="MCQ",
                answer={"mta": True},
                is_mta=True,
            )

        # Check single letter (MCQ)
        single_match = _SINGLE_LETTER_RE.match(raw)
        if single_match:
            letter = single_match.group(1).upper()
            return AnswerKeyEntry(
                question_no=q_no,
                raw_answer=raw,
                qtype="MCQ",
                answer={"correct": [letter]},
            )

        # Check multiple letters (MSQ)
        multi_match = _MULTI_LETTER_RE.match(raw)
        if multi_match:
            # Extract all letters
            letters = sorted(set(re.findall(r"[A-Da-d]", raw)))
            letters = [l.upper() for l in letters]
            return AnswerKeyEntry(
                question_no=q_no,
                raw_answer=raw,
                qtype="MSQ",
                answer={"correct": letters},
            )

        # Check NAT range
        range_match = _NAT_RANGE_RE.match(raw)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            midpoint = (low + high) / 2
            return AnswerKeyEntry(
                question_no=q_no,
                raw_answer=raw,
                qtype="NAT",
                answer={"exact": midpoint, "range_low": low, "range_high": high},
            )

        # Check NAT single
        single_num = _NAT_SINGLE_RE.match(raw)
        if single_num:
            val = float(single_num.group(1))
            return AnswerKeyEntry(
                question_no=q_no,
                raw_answer=raw,
                qtype="NAT",
                answer={"exact": val, "range_low": val, "range_high": val},
            )

        # Fallback: try to parse letters more loosely
        letters_found = re.findall(r"[A-Da-d]", raw)
        if letters_found:
            letters_upper = sorted(set(l.upper() for l in letters_found))
            if len(letters_upper) == 1:
                return AnswerKeyEntry(
                    question_no=q_no, raw_answer=raw, qtype="MCQ",
                    answer={"correct": letters_upper},
                )
            else:
                return AnswerKeyEntry(
                    question_no=q_no, raw_answer=raw, qtype="MSQ",
                    answer={"correct": letters_upper},
                )

        logger.warning("unparseable_answer", question_no=q_no, raw=raw)
        return None


class QuestionCleaner:
    """Cleans and normalises extracted question text and merges answer key data."""

    def clean_and_merge(
        self,
        question_no: int,
        raw_text: str,
        raw_options: dict[str, str] | None,
        answer_entry: AnswerKeyEntry | None,
        marks_map: dict[int, int],
        has_figure: bool,
        parse_confidence: float,
    ) -> CleanedQuestion:
        """Clean a raw question and merge with answer key data.

        Args:
            question_no: The question number.
            raw_text: Raw extracted question text.
            raw_options: Raw option dict or None.
            answer_entry: Matching answer key entry, or None.
            marks_map: Section-header-derived marks map (question_no → marks).
            has_figure: Whether the question references a figure.
            parse_confidence: Confidence from the PDF parser.

        Returns:
            A CleanedQuestion ready for DB insertion.
        """
        # Normalise text
        cleaned_text = self._normalise_text(raw_text)

        # Normalise options
        cleaned_options = None
        if raw_options:
            cleaned_options = {k: self._normalise_text(v) for k, v in raw_options.items()}

        # Determine qtype from answer key (not from option count)
        qtype = "MCQ"  # default
        answer: dict[str, Any] = {"correct": []}
        is_mta = False
        if answer_entry:
            qtype = answer_entry.qtype
            answer = answer_entry.answer
            is_mta = answer_entry.is_mta

        # Determine marks from section headers
        marks = marks_map.get(question_no, 1)  # Default to 1 if not found

        # Compute text hash for dedup
        text_hash = self._compute_text_hash(cleaned_text)

        # Determine parse status
        parse_status = "parsed"
        if parse_confidence < 0.7 or answer_entry is None:
            parse_status = "review_needed"

        return CleanedQuestion(
            question_no=question_no,
            text=cleaned_text,
            options=cleaned_options,
            qtype=qtype,
            marks=marks,
            answer=answer,
            has_figure=has_figure,
            is_mta=is_mta,
            text_hash=text_hash,
            confidence=parse_confidence,
            parse_status=parse_status,
        )

    def _normalise_text(self, text: str) -> str:
        """Normalise question text: fix Unicode, strip excessive whitespace."""
        # Normalise Unicode (NFC form)
        text = unicodedata.normalize("NFC", text)
        # Replace common math-symbol mojibake
        replacements = {
            "→": "\\to",
            "≤": "\\leq",
            "≥": "\\geq",
            "≠": "\\neq",
            "∞": "\\infty",
            "α": "\\alpha",
            "β": "\\beta",
            "Σ": "\\Sigma",
            "π": "\\pi",
            "×": "\\times",
            "÷": "\\div",
        }
        for char, latex in replacements.items():
            text = text.replace(char, latex)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def compute_text_hash(text: str) -> str:
        """Compute SHA-256 hash of normalised text for dedup.

        Normalisation: lowercase, strip all whitespace and punctuation.

        Args:
            text: The question text.

        Returns:
            Hex-encoded SHA-256 hash string (64 chars).
        """
        normalised = re.sub(r"[\s\W]+", "", text.lower())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    def _compute_text_hash(self, text: str) -> str:
        """Instance method wrapper for compute_text_hash."""
        return self.compute_text_hash(text)
