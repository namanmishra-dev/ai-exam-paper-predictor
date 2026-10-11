"""Initial schema with pgvector extension.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Read embedding dimension from env, default 384
import os

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIMENSION", "384"))


def upgrade() -> None:
    # ── Extensions ───────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # ── Enum Types ───────────────────────────────────────────────────────
    question_type_enum = postgresql.ENUM("MCQ", "MSQ", "NAT", name="question_type_enum", create_type=False)
    difficulty_enum = postgresql.ENUM("easy", "medium", "hard", name="difficulty_level_enum", create_type=False)
    source_enum = postgresql.ENUM("pyq", "generated", name="question_source_enum", create_type=False)
    parse_status_enum = postgresql.ENUM("raw", "parsed", "review_needed", "parse_failed", name="parse_status_enum", create_type=False)
    tag_status_enum = postgresql.ENUM("untagged", "suggested", "disagreement", "verified", "rejected", name="tag_status_enum", create_type=False)
    priority_bucket_enum = postgresql.ENUM("MUST_DO", "SHOULD_DO", "SKIP_IF_SHORT", name="priority_bucket_enum", create_type=False)
    job_status_enum = postgresql.ENUM("pending", "processing", "completed", "failed", name="job_status_enum", create_type=False)

    # Create all enums
    for e in [question_type_enum, difficulty_enum, source_enum, parse_status_enum,
              tag_status_enum, priority_bucket_enum, job_status_enum]:
        e.create(op.get_bind(), checkfirst=True)

    # ── Subjects ─────────────────────────────────────────────────────────
    op.create_table(
        "subjects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Topics ───────────────────────────────────────────────────────────
    op.create_table(
        "topics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject_id", sa.String(64), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_topic_id", sa.String(64), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("syllabus_order", sa.Integer, default=0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_topics_subject", "topics", ["subject_id"])
    op.create_index("idx_topics_parent", "topics", ["parent_topic_id"])

    # ── Topic Priorities ─────────────────────────────────────────────────
    op.create_table(
        "topic_priorities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("topic_id", sa.String(64), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("weighted_marks", sa.Numeric(8, 4), nullable=False),
        sa.Column("consistency", sa.Numeric(6, 4), nullable=False),
        sa.Column("trend", sa.Numeric(8, 4), nullable=False),
        sa.Column("gap", sa.Numeric(6, 4), nullable=False),
        sa.Column("priority_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("bucket", priority_bucket_enum, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("total_historical_appearances", sa.Integer, default=0, nullable=False),
        sa.Column("avg_marks_per_year", sa.Numeric(6, 2), default=0.0, nullable=False),
        sa.Column("last_appeared_year", sa.Integer, nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_topic_priorities_bucket", "topic_priorities", ["bucket"])
    op.create_index("idx_topic_priorities_score", "topic_priorities", ["priority_score"])

    # ── Questions ────────────────────────────────────────────────────────
    op.create_table(
        "questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject_id", sa.String(64), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("classified_subject", sa.String(64), nullable=False),
        sa.Column("topic_id", sa.String(64), sa.ForeignKey("topics.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("subtopic_id", sa.String(64), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", source_enum, nullable=False, server_default="pyq"),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("set_no", sa.Integer, nullable=True),
        sa.Column("question_no", sa.Integer, nullable=True),
        sa.Column("provenance", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("qtype", question_type_enum, nullable=False),
        sa.Column("marks", sa.SmallInteger, nullable=False),
        sa.Column("difficulty", difficulty_enum, nullable=False, server_default="medium"),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("options", postgresql.JSONB, nullable=True),
        sa.Column("answer", postgresql.JSONB, nullable=False),
        sa.Column("solution_text", sa.Text, nullable=False, server_default=""),
        sa.Column("has_figure", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("figure_path", sa.String(512), nullable=True),
        sa.Column("parse_status", parse_status_enum, nullable=False, server_default="raw"),
        sa.Column("tag_status", tag_status_enum, nullable=False, server_default="untagged"),
        sa.Column("tag_pass_1", postgresql.JSONB, nullable=True),
        sa.Column("tag_pass_2", postgresql.JSONB, nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("verification_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Add vector column with configurable dimension
    op.execute(f"ALTER TABLE questions ADD COLUMN embedding vector({EMBEDDING_DIM})")

    # Indices and constraints
    op.create_unique_constraint("uq_question_identity", "questions", ["subject_id", "year", "set_no", "question_no"])
    op.create_index("idx_questions_topic_diff", "questions", ["topic_id", "difficulty", "qtype", "marks"])
    op.create_index("idx_questions_source_status", "questions", ["source", "parse_status"])
    op.create_index("idx_questions_year", "questions", ["year"])
    op.create_index("idx_questions_classified_subject", "questions", ["classified_subject"])
    op.create_index("idx_questions_tag_status", "questions", ["tag_status"])
    op.create_index("idx_questions_text_hash", "questions", ["text_hash"])
    op.execute("CREATE INDEX idx_questions_embedding ON questions USING hnsw (embedding vector_cosine_ops)")

    # ── Mock Papers ──────────────────────────────────────────────────────
    op.create_table(
        "mock_papers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subject_id", sa.String(64), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("total_marks", sa.SmallInteger, nullable=False),
        sa.Column("duration_minutes", sa.SmallInteger, nullable=False),
        sa.Column("blueprint", postgresql.JSONB, nullable=False),
        sa.Column("validation_proof", postgresql.JSONB, nullable=False),
        sa.Column("seed", sa.BigInteger, nullable=True),
        sa.Column("is_template", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_mock_papers_subject", "mock_papers", ["subject_id"])

    # ── Mock Paper Questions ─────────────────────────────────────────────
    op.create_table(
        "mock_paper_questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("mock_paper_id", sa.String(64), sa.ForeignKey("mock_papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(64), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("section_order", sa.SmallInteger, nullable=False),
        sa.Column("allocated_marks", sa.SmallInteger, nullable=False),
        sa.Column("negative_marks", sa.Numeric(4, 2), nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_paper_order", "mock_paper_questions", ["mock_paper_id", "section_order"])
    op.create_index("idx_mpq_paper", "mock_paper_questions", ["mock_paper_id"])

    # ── Attempts ─────────────────────────────────────────────────────────
    op.create_table(
        "attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("mock_paper_id", sa.String(64), sa.ForeignKey("mock_papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("total_score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("max_marks", sa.SmallInteger, nullable=False),
        sa.Column("accuracy", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analytics_summary", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("idx_attempts_session", "attempts", ["session_id"])
    op.create_index("idx_attempts_paper", "attempts", ["mock_paper_id"])

    # ── Attempt Answers ──────────────────────────────────────────────────
    op.create_table(
        "attempt_answers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("attempt_id", sa.String(64), sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(64), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_response", postgresql.JSONB, nullable=True),
        sa.Column("is_correct", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_attempted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("marks_awarded", sa.Numeric(4, 2), nullable=False, server_default="0"),
        sa.Column("time_spent_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_attempt_question", "attempt_answers", ["attempt_id", "question_id"])
    op.create_index("idx_attempt_answers_attempt", "attempt_answers", ["attempt_id"])

    # ── Jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", job_status_enum, nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_table("attempt_answers")
    op.drop_table("attempts")
    op.drop_table("mock_paper_questions")
    op.drop_table("mock_papers")
    op.drop_table("jobs")
    op.drop_table("questions")
    op.drop_table("topic_priorities")
    op.drop_table("topics")
    op.drop_table("subjects")

    for enum_name in [
        "job_status_enum", "priority_bucket_enum", "tag_status_enum",
        "parse_status_enum", "question_source_enum", "difficulty_level_enum",
        "question_type_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute('DROP EXTENSION IF EXISTS "vector"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
