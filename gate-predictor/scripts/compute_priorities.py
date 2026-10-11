"""CLI Script to precompute offline topic priorities (Module 3).

Usage:
    python scripts/compute_priorities.py [--subject operating_systems] [--save-db]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.predictor import TopicPredictor
from app.analytics.schemas import SubjectPriorityResponse
from app.core.config import settings
from app.db.models.question import Question
from app.db.models.subject import Topic, TopicPriority
from app.db.session import get_session
from app.tagging.taxonomy import load_taxonomy


def compute_priorities_for_subject(
    subject_id: str = "operating_systems",
    save_to_db: bool = False,
) -> SubjectPriorityResponse:
    """Precompute topic priorities from DB question records.

    If DB is not populated or offline, falls back to loading taxonomy and pre-tagged PYQs.
    """
    data = load_taxonomy(settings.taxonomy_path)
    subject_data = data["subject"]
    taxonomy_topics = [
        {"id": t["id"], "name": t["name"], "code": t["code"]}
        for t in subject_data.get("topics", [])
    ]

    question_records: list[dict[str, Any]] = []

    # Attempt to query from DB
    try:
        with get_session() as session:
            questions = (
                session.query(Question)
                .filter(
                    Question.subject_id == subject_id,
                    Question.topic_id.isnot(None),
                    Question.tag_status == "verified",
                )
                .all()
            )
            for q in questions:
                if q.topic_id:
                    question_records.append({
                        "topic_id": q.topic_id,
                        "year": q.year,
                        "marks": float(q.marks),
                    })
    except Exception as exc:
        print(f"[WARN] DB query failed ({exc}). Using mock/local data for priority calculation.")

    # Fallback mock data if DB empty
    if not question_records:
        print("[INFO] No verified questions in DB. Using synthetic PYQ dataset for priority precomputation.")
        # Create realistic sample distribution across 10 years (2015-2024)
        years = list(range(2015, 2025))
        topic_ids = [t["id"] for t in taxonomy_topics]

        import random
        rng = random.Random(42)
        for y in years:
            for tid in topic_ids:
                if rng.random() > 0.3:  # 70% appearance probability
                    marks = rng.choice([1.0, 2.0, 3.0, 4.0])
                    question_records.append({
                        "topic_id": tid,
                        "year": y,
                        "marks": marks,
                    })

    predictor = TopicPredictor()
    response = predictor.predict(
        subject_id=subject_id,
        subject_name=subject_data["name"],
        records=question_records,
        taxonomy_topics=taxonomy_topics,
    )

    # Save to DB if requested
    if save_to_db:
        try:
            with get_session() as session:
                for item in response.all_topics:
                    # Check if priority record exists
                    existing = (
                        session.query(TopicPriority)
                        .filter(TopicPriority.topic_id == item.topic_id)
                        .first()
                    )
                    if existing:
                        existing.weighted_marks = item.weighted_marks
                        existing.consistency = item.consistency
                        existing.trend = item.trend
                        existing.gap = item.gap
                        existing.priority_score = item.priority_score
                        existing.bucket = item.bucket
                        existing.rationale = item.rationale
                        existing.confidence = item.confidence
                        existing.total_historical_appearances = item.total_historical_appearances
                        existing.avg_marks_per_year = item.avg_marks_per_year
                        existing.last_appeared_year = item.last_appeared_year
                    else:
                        tp = TopicPriority(
                            id=f"prio_{item.topic_id}",
                            topic_id=item.topic_id,
                            weighted_marks=item.weighted_marks,
                            consistency=item.consistency,
                            trend=item.trend,
                            gap=item.gap,
                            priority_score=item.priority_score,
                            bucket=item.bucket,
                            rationale=item.rationale,
                            confidence=item.confidence,
                            total_historical_appearances=item.total_historical_appearances,
                            avg_marks_per_year=item.avg_marks_per_year,
                            last_appeared_year=item.last_appeared_year,
                        )
                        session.add(tp)
                session.commit()
                print("[SUCCESS] Topic priorities saved to database.")
        except Exception as exc:
            print(f"[ERROR] Failed to save priorities to DB: {exc}")

    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute topic priority scores.")
    parser.add_argument("--subject", default="operating_systems", help="Subject ID")
    parser.add_argument("--save-db", action="store_true", help="Save computed priorities to DB")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    response = compute_priorities_for_subject(args.subject, save_to_db=args.save_db)

    if args.json:
        print(response.model_dump_json(indent=2))
        return

    print("=" * 80)
    print(f"GATE TOPIC PRIORITIES — {response.subject_name.upper()}")
    print("=" * 80)
    print(f"Disclaimer: {response.disclaimer}\n")

    print(f"[MUST-DO TOPICS] ({len(response.must_do_topics)} topics):")
    for item in response.must_do_topics:
        print(f"  - [{item.topic_code}] {item.topic_name:<35} | Score: {item.priority_score:.4f} | {item.confidence.upper()} confidence")
        print(f"    Rationale: {item.rationale}")

    print(f"\n[SHOULD-DO TOPICS] ({len(response.should_do_topics)} topics):")
    for item in response.should_do_topics:
        print(f"  - [{item.topic_code}] {item.topic_name:<35} | Score: {item.priority_score:.4f} | {item.confidence.upper()} confidence")
        print(f"    Rationale: {item.rationale}")

    print(f"\n[SKIP-IF-SHORT TOPICS] ({len(response.skip_if_short_topics)} topics):")
    for item in response.skip_if_short_topics:
        print(f"  - [{item.topic_code}] {item.topic_name:<35} | Score: {item.priority_score:.4f} | {item.confidence.upper()} confidence")
        print(f"    Rationale: {item.rationale}")


if __name__ == "__main__":
    main()
