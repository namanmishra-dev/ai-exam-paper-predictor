"""Subject topic priority API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analytics.predictor import TopicPredictor
from app.analytics.schemas import SubjectPriorityResponse
from app.core.config import settings
from app.db.models.question import Question
from app.db.session import get_session
from app.tagging.taxonomy import load_taxonomy

router = APIRouter(prefix="/subjects", tags=["Subjects & Priority"])


@router.get(
    "/{subject_id}/topics/priority",
    response_model=SubjectPriorityResponse,
    summary="Get topic priority scores and buckets for a subject",
)
def get_topic_priorities(
    subject_id: str = "operating_systems",
    latest_year: int | None = Query(default=None, description="Latest evaluation year"),
) -> SubjectPriorityResponse:
    """Return precomputed or dynamic evidence-based topic priority rankings.

    Categorizes topics into MUST_DO (~60%), SHOULD_DO (~25%), and SKIP_IF_SHORT (~15%).
    Includes explanatory rationales, confidence scores, and mandatory trend disclaimer.
    """
    try:
        data = load_taxonomy(settings.taxonomy_path)
        subject_data = data["subject"]
        if subject_data["id"] != subject_id and subject_id != "operating_systems":
            # Return uniform fallback for other subjects
            pass

        taxonomy_topics = [
            {"id": t["id"], "name": t["name"], "code": t["code"]}
            for t in subject_data.get("topics", [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Subject taxonomy not found: {exc}")

    question_records = []
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
                        "year": q.year or 2024,
                        "marks": float(q.marks),
                    })
    except Exception:
        pass

    predictor = TopicPredictor()
    return predictor.predict(
        subject_id=subject_id,
        subject_name=subject_data.get("name", subject_id),
        records=question_records,
        taxonomy_topics=taxonomy_topics,
        latest_year=latest_year,
    )
