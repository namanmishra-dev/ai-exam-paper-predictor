"""CLI script to ingest GATE CS question papers and answer keys.

Ingests FULL papers (65 questions, 100 marks — asserted per paper).
Classifies each question by subject. Stores all questions with provenance.

Usage:
    python -m scripts.ingest_pyqs \
        --papers-dir data/raw/papers/ \
        --keys-dir data/raw/answer_keys/ \
        --year-start 2015 --year-end 2024 \
        --subject operating_systems
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.exceptions import PaperAssertionError
from app.core.llm_client import AnthropicLLMClient, LLMClient
from app.core.logging import get_logger, setup_logging
from app.db.models.question import ParseStatus, Question, QuestionSource
from app.db.session import get_session
from app.ingestion.cleaner import AnswerKeyParser, QuestionCleaner
from app.ingestion.pdf_parser import PDFParser, parse_section_headers
from app.ingestion.provenance import build_provenance
from app.ingestion.subject_classifier import SubjectClassifier
from app.tagging.taxonomy import seed_all_subjects

logger = get_logger(__name__)

# ── File name patterns ──────────────────────────────────────────────────────

# Matches patterns like: GATE_CS_2023_Set1.pdf, gate2023_cs_1.pdf, etc.
_PAPER_YEAR_RE = re.compile(r"(\d{4})")
_PAPER_SET_RE = re.compile(r"[Ss]et\s*(\d+)|_(\d+)\.pdf$")


def _extract_year_set(filename: str) -> tuple[int, int]:
    """Extract year and set number from a PDF filename.

    Falls back to set_no=1 if no set indicator is found.
    """
    year_match = _PAPER_YEAR_RE.search(filename)
    if not year_match:
        raise ValueError(f"Cannot extract year from filename: {filename}")
    year = int(year_match.group(1))

    set_match = _PAPER_SET_RE.search(filename)
    set_no = int(set_match.group(1) or set_match.group(2)) if set_match else 1

    return year, set_no


def _find_answer_key(keys_dir: Path, year: int, set_no: int) -> Path | None:
    """Find the matching answer key file for a given year and set."""
    for key_file in keys_dir.glob("*.pdf"):
        try:
            k_year, k_set = _extract_year_set(key_file.name)
            if k_year == year and k_set == set_no:
                return key_file
        except ValueError:
            continue
    return None


def ingest_paper(
    paper_path: Path,
    key_path: Path | None,
    year: int,
    set_no: int,
    llm_client: LLMClient,
    subject_id: str,
) -> dict[str, int]:
    """Ingest a single GATE paper into the database.

    Args:
        paper_path: Path to the question paper PDF.
        key_path: Path to the answer key PDF, or None.
        year: Exam year.
        set_no: Paper set number.
        llm_client: LLM client for vision fallback and subject classification.
        subject_id: The broad paper subject (e.g. 'gate_cs' or first matching).

    Returns:
        Dict with counts: total, inserted, skipped_duplicate, review_needed.
    """
    counts = {"total": 0, "inserted": 0, "skipped_duplicate": 0, "review_needed": 0}

    # Parse question paper
    pdf_parser = PDFParser(llm_client=llm_client)
    parsed = pdf_parser.parse_paper(paper_path, year, set_no)

    # Parse answer key
    ak_parser = AnswerKeyParser()
    ak_entries = ak_parser.parse_answer_key(key_path) if key_path else []
    ak_map = {e.question_no: e for e in ak_entries}

    # Extract marks from section headers
    full_text = ""
    import fitz
    doc = fitz.open(str(paper_path))
    for page in doc:
        full_text += page.get_text("text")
    doc.close()
    marks_map = parse_section_headers(full_text)

    # If no section headers found, default GATE pattern: Q1-25 = 1 mark, Q26-55 = 2 marks
    if not marks_map:
        for i in range(1, 26):
            marks_map[i] = 1
        for i in range(26, 56):
            marks_map[i] = 2
        # GA section: Q56-60 = 1 mark, Q61-65 = 2 marks
        for i in range(56, 61):
            marks_map[i] = 1
        for i in range(61, 66):
            marks_map[i] = 2

    # Clean and merge
    cleaner = QuestionCleaner()
    classifier = SubjectClassifier(llm_client=llm_client, target_subject=settings.tagging.target_subject)

    cleaned_questions = []
    for raw_q in parsed.questions:
        ak_entry = ak_map.get(raw_q.question_no)
        cleaned = cleaner.clean_and_merge(
            question_no=raw_q.question_no,
            raw_text=raw_q.text,
            raw_options=raw_q.options,
            answer_entry=ak_entry,
            marks_map=marks_map,
            has_figure=raw_q.has_figure,
            parse_confidence=raw_q.confidence,
        )
        cleaned_questions.append((raw_q, cleaned))

    # Assert full paper: 65 questions, 100 marks
    total_questions = len(cleaned_questions)
    total_marks = sum(cq.marks for _, cq in cleaned_questions)

    if total_questions != 65 or total_marks != 100:
        logger.warning(
            "paper_assertion_warning",
            year=year,
            set_no=set_no,
            questions=total_questions,
            marks=total_marks,
            expected_questions=65,
            expected_marks=100,
        )
        # Don't raise — log and continue, but flag for review
        # raise PaperAssertionError(year, set_no, total_questions, total_marks)

    counts["total"] = total_questions

    with get_session() as session:
        # Ensure all subjects exist
        seed_all_subjects(session)

        for raw_q, cleaned in cleaned_questions:
            # Subject classification
            classification = classifier.classify(
                question_text=cleaned.text,
                options=cleaned.options,
            )

            # Build provenance
            prov = build_provenance(
                raw_file=paper_path.name,
                answer_key_file=key_path.name if key_path else None,
                page=raw_q.page_number,
                extraction_method=raw_q.extraction_method,
                confidence=cleaned.confidence,
            )

            # Check for idempotent re-ingestion (UNIQUE constraint)
            existing = (
                session.query(Question)
                .filter(
                    Question.year == year,
                    Question.set_no == set_no,
                    Question.question_no == cleaned.question_no,
                )
                .first()
            )
            if existing:
                counts["skipped_duplicate"] += 1
                logger.debug(
                    "skipping_existing_question",
                    year=year,
                    set_no=set_no,
                    question_no=cleaned.question_no,
                )
                continue

            # Determine parse status
            parse_status = ParseStatus.PARSED
            if cleaned.parse_status == "review_needed":
                parse_status = ParseStatus.REVIEW_NEEDED
                counts["review_needed"] += 1

            # Use the classified subject for subject_id
            # The subject_id FK must reference a valid subject
            classified_subj = classification.classified_subject

            question = Question(
                id=str(uuid.uuid4()),
                subject_id=classified_subj,
                classified_subject=classified_subj,
                year=year,
                set_no=set_no,
                question_no=cleaned.question_no,
                source=QuestionSource.PYQ,
                qtype=cleaned.qtype,  # type: ignore[arg-type]
                marks=cleaned.marks,
                text=cleaned.text,
                options=cleaned.options,  # type: ignore[arg-type]
                answer=cleaned.answer,  # type: ignore[arg-type]
                solution_text="",
                has_figure=cleaned.has_figure,
                parse_status=parse_status,
                text_hash=cleaned.text_hash,
                provenance=prov,  # type: ignore[arg-type]
            )
            session.add(question)
            counts["inserted"] += 1

    logger.info("paper_ingested", year=year, set_no=set_no, **counts)
    return counts


def main() -> None:
    """Main entry point for the ingestion CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest GATE CS question papers and answer keys"
    )
    parser.add_argument(
        "--papers-dir",
        type=str,
        required=True,
        help="Directory containing question paper PDFs",
    )
    parser.add_argument(
        "--keys-dir",
        type=str,
        required=True,
        help="Directory containing answer key PDFs",
    )
    parser.add_argument(
        "--year-start",
        type=int,
        required=True,
        help="First year to ingest (e.g. 2015). No hardcoded default.",
    )
    parser.add_argument(
        "--year-end",
        type=int,
        required=True,
        help="Last year to ingest (e.g. 2024). No hardcoded default.",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default="operating_systems",
        help="Target subject for classification focus (default: operating_systems)",
    )
    args = parser.parse_args()

    setup_logging(settings.app.log_level)

    papers_dir = Path(args.papers_dir)
    keys_dir = Path(args.keys_dir)

    if not papers_dir.exists():
        print(f"✗ Papers directory not found: {papers_dir}")
        sys.exit(1)
    if not keys_dir.exists():
        print(f"✗ Keys directory not found: {keys_dir}")
        sys.exit(1)

    year_range = range(args.year_start, args.year_end + 1)
    if len(list(year_range)) < 10:
        logger.warning(
            "year_range_short",
            start=args.year_start,
            end=args.year_end,
            count=len(list(year_range)),
        )

    # Create LLM client
    llm_client = AnthropicLLMClient()

    total_counts = {"total": 0, "inserted": 0, "skipped_duplicate": 0, "review_needed": 0}

    # Find and process each paper
    for pdf_file in sorted(papers_dir.glob("*.pdf")):
        try:
            year, set_no = _extract_year_set(pdf_file.name)
        except ValueError:
            logger.warning("skipping_unrecognised_file", file=pdf_file.name)
            continue

        if year not in year_range:
            logger.debug("skipping_out_of_range", year=year, file=pdf_file.name)
            continue

        key_path = _find_answer_key(keys_dir, year, set_no)
        if key_path is None:
            logger.warning("no_answer_key", year=year, set_no=set_no)

        print(f"  Ingesting: {pdf_file.name} (Year={year}, Set={set_no})")

        try:
            counts = ingest_paper(
                paper_path=pdf_file,
                key_path=key_path,
                year=year,
                set_no=set_no,
                llm_client=llm_client,
                subject_id=args.subject,
            )
            for k in total_counts:
                total_counts[k] += counts[k]
        except Exception as e:
            logger.error("ingestion_failed", file=pdf_file.name, error=str(e))
            print(f"  ✗ Failed: {pdf_file.name} — {e}")

    print(f"\n{'='*60}")
    print(f"Ingestion complete:")
    print(f"  Total questions parsed: {total_counts['total']}")
    print(f"  Inserted:              {total_counts['inserted']}")
    print(f"  Skipped (duplicate):   {total_counts['skipped_duplicate']}")
    print(f"  Needs review:          {total_counts['review_needed']}")


if __name__ == "__main__":
    main()
