"""CLI script to tag questions with topics using dual-pass LLM tagging.

Only tags questions classified as the target subject.
Exports review queue CSV for human verification.

Usage:
    python -m scripts.tag_questions --subject operating_systems
    python -m scripts.tag_questions --subject operating_systems --batch-size 10 --export-review
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.llm_client import AnthropicLLMClient
from app.core.logging import get_logger, setup_logging
from app.db.models.question import ParseStatus, Question, TagStatus
from app.db.session import get_session
from app.tagging.classifier import tag_batch
from app.tagging.review_queue import export_review_queue
from app.tagging.taxonomy import get_taxonomy_tree, load_taxonomy

logger = get_logger(__name__)


def main() -> None:
    """Main entry point for the tagging CLI."""
    parser = argparse.ArgumentParser(
        description="Tag GATE CS questions with topics using dual-pass LLM tagging"
    )
    parser.add_argument(
        "--subject",
        type=str,
        required=True,
        help="Target subject ID for topic tagging (e.g. operating_systems)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.tagging.tagging_batch_size,
        help=f"Number of questions to tag per batch (default: {settings.tagging.tagging_batch_size})",
    )
    parser.add_argument(
        "--export-review",
        action="store_true",
        help="Export review queue CSV after tagging",
    )
    parser.add_argument(
        "--review-output",
        type=str,
        default="data/processed/review_queue.csv",
        help="Output path for review CSV (default: data/processed/review_queue.csv)",
    )
    parser.add_argument(
        "--taxonomy-path",
        type=str,
        default=None,
        help="Path to taxonomy.yaml (default: data/taxonomy.yaml)",
    )
    args = parser.parse_args()

    setup_logging(settings.app.log_level)

    # Load taxonomy
    taxonomy_path = Path(args.taxonomy_path) if args.taxonomy_path else settings.taxonomy_path
    taxonomy_data = load_taxonomy(taxonomy_path)
    taxonomy_tree = get_taxonomy_tree(taxonomy_data)

    # Create LLM client
    llm_client = AnthropicLLMClient()

    total_tagged = 0
    total_agreed = 0
    total_disagreements = 0

    with get_session() as session:
        # Find questions to tag: parsed, classified as target subject, not yet tagged
        questions = (
            session.query(Question)
            .filter(
                Question.classified_subject == args.subject,
                Question.parse_status == ParseStatus.PARSED,
                Question.tag_status == TagStatus.UNTAGGED,
            )
            .order_by(Question.year, Question.set_no, Question.question_no)
            .all()
        )

        print(f"Found {len(questions)} untagged questions for {args.subject}")

        # Process in batches
        for i in range(0, len(questions), args.batch_size):
            batch = questions[i : i + args.batch_size]
            print(f"  Tagging batch {i // args.batch_size + 1} ({len(batch)} questions)...")

            results = tag_batch(
                session=session,
                llm_client=llm_client,
                taxonomy_tree=taxonomy_tree,
                subject_id=args.subject,
                questions=batch,
            )

            batch_agreed = sum(1 for r in results if r.agreed)
            batch_disagreements = sum(1 for r in results if not r.agreed)
            total_tagged += len(results)
            total_agreed += batch_agreed
            total_disagreements += batch_disagreements

            print(f"    ✓ {batch_agreed} agreed, {batch_disagreements} disagreements")

    print(f"\n{'='*60}")
    print(f"Tagging complete:")
    print(f"  Total tagged:    {total_tagged}")
    print(f"  Agreed:          {total_agreed}")
    print(f"  Disagreements:   {total_disagreements}")

    # Export review queue if requested
    if args.export_review:
        review_path = Path(args.review_output)
        with get_session() as session:
            count = export_review_queue(session, review_path)
        print(f"  Review queue exported: {count} items → {review_path}")


if __name__ == "__main__":
    main()
