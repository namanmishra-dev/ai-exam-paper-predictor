"""Question model with split parse_status / tag_status, dual tagging, and dedup hash."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base


class QuestionType(str, enum.Enum):
    """GATE question type, detected from the answer key."""

    MCQ = "MCQ"
    MSQ = "MSQ"
    NAT = "NAT"


class DifficultyLevel(str, enum.Enum):
    """Question difficulty level."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionSource(str, enum.Enum):
    """Origin of the question record."""

    PYQ = "pyq"
    GENERATED = "generated"


class ParseStatus(str, enum.Enum):
    """Tracks the parsing pipeline stage.

    - raw: just inserted, not yet validated
    - parsed: successfully extracted and cleaned
    - review_needed: low-confidence parse or vision-extracted, needs human check
    - parse_failed: extraction failed, record kept for audit
    """

    RAW = "raw"
    PARSED = "parsed"
    REVIEW_NEEDED = "review_needed"
    PARSE_FAILED = "parse_failed"


class TagStatus(str, enum.Enum):
    """Tracks the tagging pipeline stage.

    - untagged: not yet classified/tagged
    - suggested: LLM dual-pass agreed, awaiting human verification
    - disagreement: LLM dual-pass disagreed, needs human review
    - verified: human-approved via CSV import
    - rejected: human rejected the question
    """

    UNTAGGED = "untagged"
    SUGGESTED = "suggested"
    DISAGREEMENT = "disagreement"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Question(Base):
    """Unified PYQ and generated question bank entry."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # ── Subject & Classification ─────────────────────────────────────────
    subject_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    classified_subject: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="LLM-classified subject (e.g. operating_systems)"
    )
    topic_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=True
    )
    subtopic_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )

    # ── Provenance ───────────────────────────────────────────────────────
    source: Mapped[QuestionSource] = mapped_column(
        Enum(QuestionSource, name="question_source_enum"), default=QuestionSource.PYQ, nullable=False
    )
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    set_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # type: ignore[assignment]

    # ── Content ──────────────────────────────────────────────────────────
    qtype: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type_enum"), nullable=False
    )
    marks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level_enum"), default=DifficultyLevel.MEDIUM, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False)  # type: ignore[assignment]
    solution_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    has_figure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    figure_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Pipeline Status (split per user requirement) ─────────────────────
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status_enum"), default=ParseStatus.RAW, nullable=False
    )
    tag_status: Mapped[TagStatus] = mapped_column(
        Enum(TagStatus, name="tag_status_enum"), default=TagStatus.UNTAGGED, nullable=False
    )

    # ── Dual Tagging Results ─────────────────────────────────────────────
    tag_pass_1: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    tag_pass_2: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]

    # ── Dedup & Quality ──────────────────────────────────────────────────
    text_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="SHA-256 of normalised question text for dedup"
    )
    verification_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # type: ignore[assignment]
    embedding: Mapped[list | None] = mapped_column(  # type: ignore[assignment]
        Vector(settings.embedding.embedding_dimension), nullable=True
    )

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("subject_id", "year", "set_no", "question_no", name="uq_question_identity"),
        Index("idx_questions_topic_diff", "topic_id", "difficulty", "qtype", "marks"),
        Index("idx_questions_source_status", "source", "parse_status"),
        Index("idx_questions_year", "year"),
        Index("idx_questions_classified_subject", "classified_subject"),
        Index("idx_questions_tag_status", "tag_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Question id={self.id!r} year={self.year} "
            f"q={self.question_no} subject={self.classified_subject!r}>"
        )
