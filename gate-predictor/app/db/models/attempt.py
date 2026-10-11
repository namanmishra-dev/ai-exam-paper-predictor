"""Attempt and AttemptAnswer models for student submissions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Attempt(Base):
    """A student's attempt at a mock paper."""

    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mock_paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mock_papers.id", ondelete="RESTRICT"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    total_score: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0, nullable=False)
    max_marks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    accuracy: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analytics_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # type: ignore[assignment]

    # Relationships
    answers: Mapped[list[AttemptAnswer]] = relationship(
        "AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_attempts_session", "session_id"),
        Index("idx_attempts_paper", "mock_paper_id"),
    )

    def __repr__(self) -> str:
        return f"<Attempt id={self.id!r} score={self.total_score}/{self.max_marks}>"


class AttemptAnswer(Base):
    """A student's answer to a single question in an attempt."""

    __tablename__ = "attempt_answers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    user_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marks_awarded: Mapped[float] = mapped_column(Numeric(4, 2), default=0.0, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    attempt: Mapped[Attempt] = relationship("Attempt", back_populates="answers")

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
        Index("idx_attempt_answers_attempt", "attempt_id"),
    )

    def __repr__(self) -> str:
        return f"<AttemptAnswer attempt={self.attempt_id!r} q={self.question_id!r}>"
