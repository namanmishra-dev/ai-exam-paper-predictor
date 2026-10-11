"""CLI Script to pre-fill the Question Bank offline with verified generated questions (Module 5).

Usage:
    python scripts/fill_bank.py [--count-per-topic 3] [--save-db]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.db.models.question import DifficultyLevel, QuestionType
from app.db.session import get_session
from app.generation.generator import QuestionGenerator
from app.core.llm_client import MockLLMClient
from app.tagging.taxonomy import load_taxonomy


def fill_question_bank(
    count_per_topic: int = 3,
    save_to_db: bool = False,
) -> None:
    """Batch generate and verify questions for each taxonomy topic."""
    data = load_taxonomy(settings.taxonomy_path)
    topics = data["subject"].get("topics", [])

    print("=" * 80)
    print(f"QUESTION BANK BATCH GENERATOR — {data['subject']['name'].upper()}")
    print("=" * 80)
    print(f"Topics to generate: {len(topics)} | Target per topic: {count_per_topic}\n")

    # Use MockLLMClient if ANTHROPIC_API_KEY is missing
    llm_client = MockLLMClient()
    generator = QuestionGenerator(llm_client=llm_client)

    qtype_cycle = [QuestionType.MCQ, QuestionType.MSQ, QuestionType.NAT]
    diff_cycle = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]

    session = None
    if save_to_db:
        try:
            session = get_session()
        except Exception as exc:
            print(f"[WARN] DB session creation failed ({exc}). Running offline mock batch.")

    total_generated = 0
    total_verified = 0

    for topic in topics:
        tid = topic["id"]
        tname = topic["name"]
        print(f"-> Generating for topic: [{topic['code']}] {tname}...")

        for i in range(count_per_topic):
            qtype = qtype_cycle[i % len(qtype_cycle)]
            diff = diff_cycle[i % len(diff_cycle)]
            marks = 1 if i % 2 == 0 else 2

            question, verif = generator.generate_question(
                topic_id=tid,
                topic_name=tname,
                difficulty=diff,
                qtype=qtype,
                marks=marks,
                session=session if save_to_db else None,
            )

            total_generated += 1
            if question is not None and verif.passed:
                total_verified += 1
                print(
                    f"   [VERIFIED] {qtype.value} ({diff.value}, {marks}m) - "
                    f"ID: {question.id} | Hash: {question.text_hash[:8]}"
                )
            else:
                print(
                    f"   [DISCARDED] {qtype.value} ({diff.value}, {marks}m) - "
                    f"Reasons: {', '.join(verif.failure_reasons)}"
                )

    if session is not None:
        session.close()

    print("\n" + "=" * 80)
    print(f"BATCH GENERATION COMPLETE: {total_verified}/{total_generated} questions verified.")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill question bank with generated questions.")
    parser.add_argument("--count-per-topic", type=int, default=3, help="Questions per topic")
    parser.add_argument("--save-db", action="store_true", help="Save verified questions to DB")
    args = parser.parse_args()

    fill_question_bank(count_per_topic=args.count_per_topic, save_to_db=args.save_db)


if __name__ == "__main__":
    main()
