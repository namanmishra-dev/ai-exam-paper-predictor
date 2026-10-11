"""PDF parser for GATE question papers and answer keys.

Primary: PyMuPDF (fitz) for text extraction.
Fallback: pdfplumber for table-heavy layouts.
Vision fallback: Claude vision API for scanned/math-heavy pages.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

from app.core.exceptions import ParseError
from app.core.llm_client import LLMClient, VisionExtractionResult
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RawParsedQuestion:
    """A single question extracted from a PDF page."""

    question_no: int
    text: str
    options: dict[str, str] | None = None  # {"A": "...", "B": "...", ...}
    has_figure: bool = False
    page_number: int = 0
    confidence: float = 1.0
    extraction_method: str = "pymupdf"
    raw_block: str = ""  # Original text block for debugging


@dataclass
class ParsedPaper:
    """All questions extracted from a single GATE paper PDF."""

    year: int
    set_no: int
    file_path: str
    questions: list[RawParsedQuestion] = field(default_factory=list)
    total_pages: int = 0
    warnings: list[str] = field(default_factory=list)


# ── Question boundary patterns ──────────────────────────────────────────────

# Matches "Q.1", "Q. 1", "Q1", "Question 1", "1.", "1)" at start of line
_QUESTION_START_RE = re.compile(
    r"^(?:Q\.?\s*(\d+)|Question\s+(\d+)|(\d+)\s*[.)]\s)",
    re.MULTILINE,
)

# Matches option lines: "(A)", "(a)", "A.", "A)", etc.
_OPTION_RE = re.compile(
    r"^\s*\(?([A-Da-d])\s*[.)]\s*(.*)",
    re.MULTILINE,
)

# Section header for marks: "Q.1 - Q.25 carry 1 mark each"
_SECTION_HEADER_RE = re.compile(
    r"Q\.?\s*(\d+)\s*[-–—to]+\s*Q\.?\s*(\d+)\s+carry\s+(\d+)\s+marks?\s+each",
    re.IGNORECASE,
)

# Patterns indicating low confidence
_LOW_CONFIDENCE_PATTERNS = [
    re.compile(r"[^\x00-\x7F]{3,}"),  # Long non-ASCII runs (garbled math)
    re.compile(r"\\[a-z]+\{"),         # Raw LaTeX commands (not rendered)
    re.compile(r"□|■|▪|●"),            # Placeholder symbols
]

# Figure reference patterns
_FIGURE_RE = re.compile(r"(?:figure|fig\.?|diagram|image)\s*\d*", re.IGNORECASE)


class PDFParser:
    """Extracts questions from GATE CS question paper PDFs.

    Args:
        llm_client: An LLMClient instance for Claude vision fallback.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def parse_paper(self, pdf_path: Path, year: int, set_no: int) -> ParsedPaper:
        """Parse a complete GATE question paper PDF.

        Tries PyMuPDF first. Falls back to pdfplumber for pages where
        PyMuPDF yields poor results. Uses Claude vision as a last resort
        for scanned/math-heavy pages.

        Args:
            pdf_path: Path to the question paper PDF.
            year: The GATE exam year.
            set_no: The paper set number.

        Returns:
            A ParsedPaper with all extracted questions.
        """
        if not pdf_path.exists():
            raise ParseError(f"PDF not found: {pdf_path}")

        result = ParsedPaper(
            year=year, set_no=set_no, file_path=str(pdf_path)
        )

        # Phase 1: PyMuPDF extraction
        doc = fitz.open(str(pdf_path))
        result.total_pages = len(doc)
        full_text = ""
        page_texts: dict[int, str] = {}
        low_confidence_pages: list[int] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text("text")
            page_texts[page_num] = page_text

            # Check for low-confidence indicators
            if self._is_low_confidence_page(page_text):
                low_confidence_pages.append(page_num)
            else:
                full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}"

        doc.close()

        # Phase 2: pdfplumber fallback for low-confidence pages
        if low_confidence_pages:
            logger.info(
                "pdfplumber_fallback",
                pages=low_confidence_pages,
                file=str(pdf_path),
            )
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num in low_confidence_pages:
                    if page_num < len(pdf.pages):
                        page_text = pdf.pages[page_num].extract_text() or ""
                        if self._is_low_confidence_page(page_text):
                            # Phase 3: Claude vision fallback
                            vision_text = self._try_vision_extraction(
                                pdf_path, page_num, year, set_no
                            )
                            if vision_text:
                                full_text += f"\n--- PAGE {page_num + 1} (VISION) ---\n{vision_text}"
                                result.warnings.append(
                                    f"Page {page_num + 1} extracted via Claude vision — needs review"
                                )
                            else:
                                result.warnings.append(
                                    f"Page {page_num + 1} could not be reliably extracted"
                                )
                        else:
                            full_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}"

        # Phase 4: Split text into individual questions
        raw_questions = self._split_into_questions(full_text, page_texts)
        result.questions = raw_questions

        logger.info(
            "paper_parsed",
            year=year,
            set_no=set_no,
            questions_found=len(raw_questions),
            low_confidence_pages=len(low_confidence_pages),
        )

        return result

    def _is_low_confidence_page(self, text: str) -> bool:
        """Check if a page's extracted text is likely garbled or incomplete."""
        if not text or len(text.strip()) < 50:
            return True
        for pattern in _LOW_CONFIDENCE_PATTERNS:
            if len(pattern.findall(text)) > 3:
                return True
        return False

    def _try_vision_extraction(
        self, pdf_path: Path, page_num: int, year: int, set_no: int
    ) -> str | None:
        """Attempt to extract text from a page image via Claude vision.

        Returns the extracted text or None if vision is unavailable or fails.
        """
        if self._llm_client is None:
            logger.warning("vision_fallback_skipped", reason="no llm_client provided")
            return None

        try:
            doc = fitz.open(str(pdf_path))
            page = doc[page_num]
            # Render page to a high-resolution PNG
            pix = page.get_pixmap(dpi=300)
            image_bytes = pix.tobytes("png")
            doc.close()

            prompt = (
                f"This is page {page_num + 1} from GATE CS {year} Set {set_no} question paper. "
                "Extract ALL questions visible on this page. For each question, provide:\n"
                "- question_no (integer)\n"
                "- text (full question text, use LaTeX for math: $...$)\n"
                "- options (dict with keys A,B,C,D and values as option text, or null for NAT)\n"
                "- has_figure (boolean)\n\n"
                "Return JSON: {\"questions\": [...], \"raw_text\": \"...\", \"confidence\": 0.0-1.0}"
            )

            vision_result = self._llm_client.extract_with_vision(
                image_bytes=image_bytes,
                media_type="image/png",
                prompt=prompt,
            )

            # Convert vision result back to text format for unified processing
            lines: list[str] = []
            for q in vision_result.questions_json:
                q_no = q.get("question_no", "?")
                q_text = q.get("text", "")
                lines.append(f"Q.{q_no} {q_text}")
                options = q.get("options")
                if options and isinstance(options, dict):
                    for key in sorted(options.keys()):
                        lines.append(f"({key}) {options[key]}")

            logger.info(
                "vision_extraction_success",
                page=page_num + 1,
                questions_found=len(vision_result.questions_json),
                confidence=vision_result.confidence,
            )
            return "\n".join(lines)

        except Exception as e:
            logger.error("vision_extraction_failed", page=page_num + 1, error=str(e))
            return None

    def _split_into_questions(
        self, full_text: str, page_texts: dict[int, str]
    ) -> list[RawParsedQuestion]:
        """Split concatenated text into individual question records."""
        questions: list[RawParsedQuestion] = []

        # Find all question boundaries
        matches = list(_QUESTION_START_RE.finditer(full_text))
        if not matches:
            logger.warning("no_questions_found_in_text")
            return questions

        for i, match in enumerate(matches):
            # Extract question number from whichever group matched
            q_no_str = match.group(1) or match.group(2) or match.group(3)
            if q_no_str is None:
                continue
            q_no = int(q_no_str)

            # Extract text block between this question and the next
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            block = full_text[start:end].strip()

            # Remove the question number prefix from the text
            text_after_num = block[match.end() - start:].strip()

            # Extract options
            options = self._extract_options(text_after_num)
            question_text = text_after_num
            if options:
                # Remove option lines from question text
                first_option_match = _OPTION_RE.search(text_after_num)
                if first_option_match:
                    question_text = text_after_num[:first_option_match.start()].strip()

            # Check for figures
            has_figure = bool(_FIGURE_RE.search(block))

            # Compute confidence
            confidence = self._compute_confidence(question_text, options, has_figure)

            # Determine page number
            page_number = self._find_page_for_position(match.start(), full_text)

            questions.append(RawParsedQuestion(
                question_no=q_no,
                text=question_text,
                options=options,
                has_figure=has_figure,
                page_number=page_number,
                confidence=confidence,
                extraction_method="pymupdf",
                raw_block=block,
            ))

        return questions

    def _extract_options(self, text: str) -> dict[str, str] | None:
        """Extract answer options (A/B/C/D) from question text."""
        options: dict[str, str] = {}
        for match in _OPTION_RE.finditer(text):
            key = match.group(1).upper()
            value = match.group(2).strip()
            options[key] = value

        if not options:
            return None
        return options if len(options) >= 2 else None

    def _compute_confidence(
        self, text: str, options: dict[str, str] | None, has_figure: bool
    ) -> float:
        """Compute a confidence score for the extraction quality."""
        confidence = 1.0

        if len(text) < 20:
            confidence -= 0.3
        if has_figure:
            confidence -= 0.15  # Figures may be lost
        for pattern in _LOW_CONFIDENCE_PATTERNS:
            if pattern.search(text):
                confidence -= 0.2
        if options and len(options) < 4:
            confidence -= 0.1  # Possibly missing options

        return max(0.0, min(1.0, confidence))

    def _find_page_for_position(self, pos: int, full_text: str) -> int:
        """Find which page a text position belongs to based on page markers."""
        page_marker_re = re.compile(r"--- PAGE (\d+)")
        last_page = 1
        for match in page_marker_re.finditer(full_text):
            if match.start() <= pos:
                last_page = int(match.group(1))
            else:
                break
        return last_page


def parse_section_headers(text: str) -> dict[int, int]:
    """Extract marks-per-question from section headers.

    Parses patterns like "Q.1 - Q.25 carry 1 mark each" to build a
    mapping of question_no → marks.

    Args:
        text: Full text of the paper (or first few pages).

    Returns:
        Dict mapping question number to marks (1 or 2).
    """
    marks_map: dict[int, int] = {}
    for match in _SECTION_HEADER_RE.finditer(text):
        start_q = int(match.group(1))
        end_q = int(match.group(2))
        marks = int(match.group(3))
        for q_no in range(start_q, end_q + 1):
            marks_map[q_no] = marks
    return marks_map
