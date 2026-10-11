"""Mock Paper endpoints (Assembly, Fetch, Submit & Score)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.assembler.schemas import AssemblyConstraintValidation, PaperBlueprint
from app.assembler.solver import PaperAssembler
from app.core.config import settings
from app.db.models.question import DifficultyLevel, Question, QuestionSource, QuestionType
from app.db.session import get_session
from app.scoring.evaluator import ScoringEngine
from app.scoring.schemas import AttemptScoreReport, SubmitAttemptRequest
from app.tagging.taxonomy import load_taxonomy

router = APIRouter(prefix="/mock-papers", tags=["Mock Papers & Scoring"])

# In-memory storage for assembled papers when DB is offline or for preview
_MOCK_PAPER_STORE: dict[str, dict[str, Any]] = {}


@router.post("", summary="Assemble a new mock paper synchronously")
def create_mock_paper(
    blueprint: PaperBlueprint | None = None,
    subject_id: str = "operating_systems",
) -> dict[str, Any]:
    """Assemble a GATE mock paper matching blueprint constraints."""
    bp = blueprint or PaperBlueprint()
    data = load_taxonomy(settings.taxonomy_path)
    taxonomy_topics = [
        {"id": t["id"], "name": t["name"], "code": t["code"]}
        for t in data["subject"].get("topics", [])
    ]

    candidate_questions: list[Question] = []
    try:
        with get_session() as session:
            candidate_questions = session.query(Question).all()
    except Exception:
        pass

    # Synthetic fallback candidates if DB empty
    if len(candidate_questions) < bp.total_questions:
        topic_ids = [t["id"] for t in taxonomy_topics]
        for i in range(1, bp.total_questions + 10):
            qtype = QuestionType.MCQ if i % 2 == 1 else (QuestionType.MSQ if i % 3 == 0 else QuestionType.NAT)
            q = Question(
                id=f"cand_q_{i}",
                subject_id=subject_id,
                classified_subject=subject_id,
                topic_id=topic_ids[i % len(topic_ids)],
                source=QuestionSource.PYQ if i % 2 == 0 else QuestionSource.GENERATED,
                year=2020 + (i % 5),
                qtype=qtype,
                marks=1 if i % 2 == 1 else 2,
                difficulty=DifficultyLevel.MEDIUM,
                text=f"Mock paper question {i} for topic {topic_ids[i % len(topic_ids)]}.",
                options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"} if qtype != QuestionType.NAT else None,
                answer=["A"] if qtype == QuestionType.MCQ else (["A", "B"] if qtype == QuestionType.MSQ else {"value": 5.0, "min": 4.5, "max": 5.5}),
                solution_text=f"Solution for question {i}.",
                text_hash=f"hash_cand_{i}",
            )
            candidate_questions.append(q)

    assembler = PaperAssembler()
    selected_questions, validation = assembler.assemble_paper(
        candidate_questions=candidate_questions,
        blueprint=bp,
        subject_id=subject_id,
        taxonomy_topics=taxonomy_topics,
    )

    paper_id = f"paper_{uuid.uuid4().hex[:10]}"
    paper_data = {
        "id": paper_id,
        "subject_id": subject_id,
        "title": f"GATE {data['subject']['name']} Mock Paper #{paper_id[-4:]}",
        "total_marks": validation.actual_marks,
        "total_questions": validation.actual_questions,
        "duration_minutes": bp.duration_minutes,
        "validation_report": validation.model_dump(),
        "questions": [
            {
                "id": q.id,
                "topic_id": q.topic_id,
                "qtype": q.qtype.value,
                "marks": q.marks,
                "difficulty": q.difficulty.value,
                "text": q.text,
                "options": q.options,
                "source": q.source.value,
                "year": q.year,
            }
            for q in selected_questions
        ],
        "_raw_questions": selected_questions,
    }

    _MOCK_PAPER_STORE[paper_id] = paper_data

    return {
        "paper_id": paper_id,
        "title": paper_data["title"],
        "total_marks": paper_data["total_marks"],
        "total_questions": paper_data["total_questions"],
        "duration_minutes": paper_data["duration_minutes"],
        "validation_report": validation,
        "questions_summary": f"Assembled {len(selected_questions)} questions successfully.",
    }


@router.get("/{paper_id}", summary="Get assembled mock paper details and questions")
def get_mock_paper(paper_id: str) -> dict[str, Any]:
    """Retrieve full mock paper including questions."""
    paper = _MOCK_PAPER_STORE.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Mock paper '{paper_id}' not found.")

    res = dict(paper)
    res.pop("_raw_questions", None)
    return res


@router.post("/{paper_id}/submit", response_model=AttemptScoreReport, summary="Submit and score mock paper attempt")
def submit_mock_paper_attempt(
    paper_id: str,
    submission: SubmitAttemptRequest,
) -> AttemptScoreReport:
    """Evaluate submitted user attempt and return score report with topic analytics."""
    paper = _MOCK_PAPER_STORE.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Mock paper '{paper_id}' not found.")

    raw_questions: list[Question] = paper["_raw_questions"]
    submission.mock_paper_id = paper_id

    scoring_engine = ScoringEngine()
    report = scoring_engine.evaluate_attempt(
        submission=submission,
        paper_questions=raw_questions,
    )

    return report
