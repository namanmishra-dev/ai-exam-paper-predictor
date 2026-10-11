"""MockPaper and MockPaperQuestion models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MockPaper(Base):
    """An assembled mock exam paper."""

    __tablename__ = "mock_papers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_marks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    blueprint: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    validation_proof: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    questions: Mapped[list[MockPaperQuestion]] = relationship(
        "MockPaperQuestion", back_populates="mock_paper", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_mock_papers_subject", "subject_id"),)

    def __repr__(self) -> str:
        return f"<MockPaper id={self.id!r} marks={self.total_marks}>"


class MockPaperQuestion(Base):
    """Maps a question to its position in a mock paper."""

    __tablename__ = "mock_paper_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mock_paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("mock_papers.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    section_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    allocated_marks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    negative_marks: Mapped[float] = mapped_column(Numeric(4, 2), default=0.0, nullable=False)

    # Relationships
    mock_paper: Mapped[MockPaper] = relationship("MockPaper", back_populates="questions")

    __table_args__ = (
        UniqueConstraint("mock_paper_id", "section_order", name="uq_paper_order"),
        Index("idx_mpq_paper", "mock_paper_id"),
    )

    def __repr__(self) -> str:
        return f"<MockPaperQuestion paper={self.mock_paper_id!r} order={self.section_order}>"
