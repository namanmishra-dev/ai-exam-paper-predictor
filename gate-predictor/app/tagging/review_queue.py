"""Review queue for human verification of parsed and tagged questions.

Exports questions needing review to CSV and imports human corrections.
A question only becomes "verified" through this CSV import process.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models.question import ParseStatus, Question, TagStatus

logger = get_logger(__name__)

# CSV column order for the review queue
_CSV_COLUMNS = [
    "question_id",
    "year",
    "set_no",
    "question_no",
    "text_preview",
    "classified_subject",
    "proposed_topic",
    "proposed_subtopic",
    "proposed_difficulty",
    "tag_pass_1_topic",
    "tag_pass_1_subtopic",
    "tag_pass_2_topic",
    "tag_pass_2_subtopic",
    "parse_status",
    "tag_status",
    "confidence",
    "action",  # Human fills: "verify", "reject", or corrected topic/subtopic/difficulty
    "corrected_topic",
    "corrected_subtopic",
    "corrected_difficulty",
    "notes",
]


def export_review_queue(session: Session, output_path: Path) -> int:
    """Export all questions needing review to a CSV file.

    Includes questions with:
    - parse_status = review_needed
    - tag_status = suggested or disagreement

    Args:
        session: A SQLAlchemy session.
        output_path: Path to write the CSV file.

    Returns:
        Number of questions exported.
    """
    questions = (
        session.query(Question)
        .filter(
            or_(
                Question.parse_status == ParseStatus.REVIEW_NEEDED,
                Question.tag_status.in_([TagStatus.SUGGESTED, TagStatus.DISAGREEMENT]),
            )
        )
        .order_by(Question.year, Question.set_no, Question.question_no)
        .all()
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        writer.writeheader()

        for q in questions:
            tag1 = q.tag_pass_1 or {}
            tag2 = q.tag_pass_2 or {}

            writer.writerow({
                "question_id": q.id,
                "year": q.year,
                "set_no": q.set_no,
                "question_no": q.question_no,
                "text_preview": q.text[:120].replace("\n", " "),
                "classified_subject": q.classified_subject,
                "proposed_topic": q.topic_id or "",
                "proposed_subtopic": q.subtopic_id or "",
                "proposed_difficulty": q.difficulty.value if q.difficulty else "",
                "tag_pass_1_topic": tag1.get("topic_id", ""),
                "tag_pass_1_subtopic": tag1.get("subtopic_id", ""),
                "tag_pass_2_topic": tag2.get("topic_id", ""),
                "tag_pass_2_subtopic": tag2.get("subtopic_id", ""),
                "parse_status": q.parse_status.value if q.parse_status else "",
                "tag_status": q.tag_status.value if q.tag_status else "",
                "confidence": q.provenance.get("confidence", ""),
                "action": "",
                "corrected_topic": "",
                "corrected_subtopic": "",
                "corrected_difficulty": "",
                "notes": "",
            })

    logger.info("review_queue_exported", path=str(output_path), count=len(questions))
    return len(questions)


def import_review_decisions(session: Session, csv_path: Path) -> dict[str, int]:
    """Import human review decisions from a corrected CSV file.

    Supported actions:
    - "verify": Accept proposed or corrected tags, set tag_status=verified
    - "reject": Set tag_status=rejected
    - (blank): Skip this row

    When corrected_topic/subtopic/difficulty are filled, those override
    the proposed values. Human corrections are also stored in
    verification_metadata for audit.

    Args:
        session: A SQLAlchemy session.
        csv_path: Path to the reviewed CSV file.

    Returns:
        Dict with counts: {"verified": N, "rejected": N, "skipped": N, "errors": N}
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Review CSV not found: {csv_path}")

    counts = {"verified": 0, "rejected": 0, "skipped": 0, "errors": 0}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            question_id = row.get("question_id", "").strip()
            action = row.get("action", "").strip().lower()

            if not question_id or not action:
                counts["skipped"] += 1
                continue

            question = session.get(Question, question_id)
            if question is None:
                logger.error("review_question_not_found", id=question_id)
                counts["errors"] += 1
                continue

            if action == "verify":
                # Apply corrections if provided, otherwise keep proposed
                corrected_topic = row.get("corrected_topic", "").strip()
                corrected_subtopic = row.get("corrected_subtopic", "").strip()
                corrected_difficulty = row.get("corrected_difficulty", "").strip()

                if corrected_topic:
                    question.topic_id = corrected_topic if corrected_topic != "out_of_scope" else None
                if corrected_subtopic:
                    question.subtopic_id = corrected_subtopic or None
                if corrected_difficulty:
                    question.difficulty = corrected_difficulty  # type: ignore[assignment]

                question.tag_status = TagStatus.VERIFIED  # type: ignore[assignment]
                question.parse_status = ParseStatus.PARSED  # type: ignore[assignment]

                # Store human corrections in verification_metadata
                corrections: dict[str, Any] = {}
                if corrected_topic:
                    corrections["corrected_topic"] = corrected_topic
                if corrected_subtopic:
                    corrections["corrected_subtopic"] = corrected_subtopic
                if corrected_difficulty:
                    corrections["corrected_difficulty"] = corrected_difficulty
                if row.get("notes", "").strip():
                    corrections["notes"] = row["notes"].strip()
                if corrections:
                    existing_meta = dict(question.verification_metadata or {})
                    existing_meta["human_review"] = corrections
                    question.verification_metadata = existing_meta  # type: ignore[assignment]

                counts["verified"] += 1
                logger.info("question_verified", id=question_id)

            elif action == "reject":
                question.tag_status = TagStatus.REJECTED  # type: ignore[assignment]
                counts["rejected"] += 1
                logger.info("question_rejected", id=question_id)

            else:
                logger.warning("unknown_action", id=question_id, action=action)
                counts["skipped"] += 1

    session.flush()
    logger.info("review_import_complete", **counts)
    return counts
