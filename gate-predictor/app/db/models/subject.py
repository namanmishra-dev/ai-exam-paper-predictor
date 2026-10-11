"""Subject, Topic (two-level taxonomy), and TopicPriority models."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PriorityBucket(str, enum.Enum):
    """Priority bucket for topic ranking."""

    MUST_DO = "MUST_DO"
    SHOULD_DO = "SHOULD_DO"
    SKIP_IF_SHORT = "SKIP_IF_SHORT"


class Subject(Base):
    """A GATE CS subject area (e.g. operating_systems, data_structures)."""

    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    # Relationships
    topics: Mapped[list[Topic]] = relationship("Topic", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject id={self.id!r} name={self.name!r}>"


class Topic(Base):
    """A two-level taxonomy topic for a subject.

    Top-level topics have ``parent_topic_id=None``.
    Subtopics reference their parent via ``parent_topic_id``.
    """

    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    parent_topic_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    syllabus_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    subject: Mapped[Subject] = relationship("Subject", back_populates="topics")
    parent: Mapped[Topic | None] = relationship(
        "Topic", remote_side="Topic.id", back_populates="children"
    )
    children: Mapped[list[Topic]] = relationship("Topic", back_populates="parent")

    __table_args__ = (
        Index("idx_topics_subject", "subject_id"),
        Index("idx_topics_parent", "parent_topic_id"),
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id!r} name={self.name!r} parent={self.parent_topic_id!r}>"


class TopicPriority(Base):
    """Precomputed priority metrics for a topic (Module 3 output)."""

    __tablename__ = "topic_priorities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    weighted_marks: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    consistency: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    trend: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    gap: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    priority_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    bucket: Mapped[PriorityBucket] = mapped_column(
        Enum(PriorityBucket, name="priority_bucket_enum"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    total_historical_appearances: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_marks_per_year: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0, nullable=False)
    last_appeared_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    topic: Mapped[Topic] = relationship("Topic")

    __table_args__ = (
        Index("idx_topic_priorities_bucket", "bucket"),
        Index("idx_topic_priorities_score", priority_score.desc()),
    )

    def __repr__(self) -> str:
        return f"<TopicPriority topic={self.topic_id!r} score={self.priority_score!r}>"
