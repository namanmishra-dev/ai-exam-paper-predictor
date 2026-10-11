"""CLI Script to execute rolling-origin backtest and generate report (Module 4).

Usage:
    python scripts/run_backtest.py [--subject operating_systems] [--output data/backtest_report.md]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.backtest import BacktestEngine
from app.analytics.predictor import QuestionRecord
from app.analytics.schemas import BacktestReport
from app.core.config import settings
from app.db.models.question import Question
from app.db.session import get_session
from app.tagging.taxonomy import load_taxonomy


def run_backtest_pipeline(
    subject_id: str = "operating_systems",
    output_path: Path | None = None,
) -> BacktestReport:
    """Execute rolling-origin backtest and save markdown report."""
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
        print(f"[WARN] DB query failed ({exc}). Generating synthetic dataset for backtest.")

    # Fallback synthetic dataset if DB empty or small
    if len(question_records) < 50:
        print("[INFO] Generating 10-year synthetic PYQ dataset for backtest evaluation...")
        years = list(range(2015, 2025))
        topic_ids = [t["id"] for t in taxonomy_topics]

        # Seeded random distribution with realistic topic weights
        rng = random.Random(2026)
        topic_weights = {tid: rng.uniform(0.2, 1.0) for tid in topic_ids}

        for y in years:
            for tid, w in topic_weights.items():
                if rng.random() < (w * 0.85):
                    # 1 to 3 questions per active topic
                    n_q = rng.randint(1, 3)
                    for _ in range(n_q):
                        marks = float(rng.choice([1, 2]))
                        question_records.append({
                            "topic_id": tid,
                            "year": y,
                            "marks": marks,
                        })

    backtester = BacktestEngine(eval_window_folds=5, history_window_years=10)
    report = backtester.run_backtest(
        subject_id=subject_id,
        records=question_records,
        taxonomy_topics=taxonomy_topics,
    )

    # Save report to markdown file
    out_file = output_path or (settings.data_dir / "backtest_report.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_content = report.to_markdown()
    out_file.write_text(markdown_content, encoding="utf-8")

    print(f"[SUCCESS] Backtest evaluation completed. Report saved to: {out_file.resolve()}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run rolling-origin backtest evaluation.")
    parser.add_argument("--subject", default="operating_systems", help="Subject ID")
    parser.add_argument("--output", type=Path, default=None, help="Output markdown file path")
    args = parser.parse_args()

    report = run_backtest_pipeline(args.subject, output_path=args.output)
    print("\n" + report.to_markdown())


if __name__ == "__main__":
    main()
