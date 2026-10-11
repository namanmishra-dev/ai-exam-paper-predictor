"""Pydantic schemas for scoring attempt submissions and analytics (Module 7)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class QuestionAnswerPayload(BaseModel):
    """User submission for a single question."""

    question_id: str
    user_answer: Any = Field(description="List of option keys for MCQ/MSQ, or float for NAT")
    time_taken_seconds: float = Field(default=0.0, ge=0.0)


class SubmitAttemptRequest(BaseModel):
    """Request payload for submitting a mock paper attempt."""

    attempt_id: str | None = None
    mock_paper_id: str
    user_id: str = Field(default="anon_session", description="Anonymous user/session ID")
    answers: list[QuestionAnswerPayload]


class QuestionScoreDetail(BaseModel):
    """Detailed score result for a single question attempt."""

    question_id: str
    qtype: str
    marks_allocated: int
    marks_obtained: float
    is_correct: bool
    user_answer: Any
    correct_answer: Any
    explanation: str
    topic_id: str | None = None


class TopicAccuracy(BaseModel):
    """Topic-level performance analytics."""

    topic_id: str
    topic_name: str
    total_questions: int
    correct_count: int
    marks_allocated: float
    marks_obtained: float
    accuracy_pct: float
    priority_bucket: str = Field(default="UNKNOWN")


class AttemptScoreReport(BaseModel):
    """Complete attempt scoring report and analytics."""

    attempt_id: str
    mock_paper_id: str
    total_score: float
    max_score: float
    accuracy_pct: float
    correct_count: int
    incorrect_count: int
    unattempted_count: int
    total_time_seconds: float
    question_details: list[QuestionScoreDetail]
    topic_analytics: list[TopicAccuracy]
    weak_topics: list[TopicAccuracy]
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
