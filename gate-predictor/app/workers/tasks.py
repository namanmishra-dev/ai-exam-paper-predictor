"""Async background Celery tasks (Module 8)."""

from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="tasks.precompute_topic_priorities")
def precompute_topic_priorities_task(subject_id: str = "operating_systems") -> dict[str, Any]:
    """Offline background task to recompute topic priority scores."""
    from scripts.compute_priorities import compute_priorities_for_subject

    response = compute_priorities_for_subject(subject_id=subject_id, save_to_db=True)
    return {
        "status": "completed",
        "subject_id": subject_id,
        "must_do_count": len(response.must_do_topics),
        "should_do_count": len(response.should_do_topics),
        "skip_count": len(response.skip_if_short_topics),
    }


@celery_app.task(name="tasks.fill_question_bank")
def fill_question_bank_task(count_per_topic: int = 3) -> dict[str, Any]:
    """Background task to generate batch questions for question bank."""
    from scripts.fill_bank import fill_question_bank

    fill_question_bank(count_per_topic=count_per_topic, save_to_db=True)
    return {
        "status": "completed",
        "count_per_topic": count_per_topic,
    }


@celery_app.task(name="tasks.generate_custom_mock_paper")
def generate_custom_mock_paper_task(
    job_id: str,
    subject_id: str,
    total_questions: int = 65,
    total_marks: float = 100.0,
) -> dict[str, Any]:
    """Async background task for generating custom mock papers."""
    from app.assembler.schemas import PaperBlueprint
    from app.api.v1.endpoints.mock_papers import create_mock_paper

    bp = PaperBlueprint(total_questions=total_questions, total_marks=total_marks)
    result = create_mock_paper(blueprint=bp, subject_id=subject_id)
    return {
        "job_id": job_id,
        "status": "completed",
        "paper_id": result["paper_id"],
    }
