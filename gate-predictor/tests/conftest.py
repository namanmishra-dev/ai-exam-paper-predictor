"""Shared test fixtures and configuration.

Uses testcontainers for real PostgreSQL + pgvector (not SQLite).
Injects MockLLMClient via DI instead of patching the SDK.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Set test environment variables BEFORE importing app modules
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_gate")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.core.llm_client import (
    MockLLMClient,
    SubjectClassification,
    TopicTagResult,
    VisionExtractionResult,
)
from app.db.base import Base
from app.db.models import *  # noqa: F401, F403 — register all models


# ── Fixtures ─────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _get_test_db_url() -> str:
    """Get the test database URL.

    Tries testcontainers first, falls back to env var.
    """
    try:
        from testcontainers.postgres import PostgresContainer

        # Use pgvector image
        container = PostgresContainer(
            image="pgvector/pgvector:pg16",
            username="test",
            password="test",
            dbname="test_gate",
            driver="psycopg2",
        )
        container.start()
        url = container.get_connection_url()
        # Ensure psycopg2 driver
        if "psycopg2" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        # Store container reference to prevent GC
        _get_test_db_url._container = container  # type: ignore[attr-defined]
        return url
    except Exception:
        # Fall back to env var (e.g. when using docker compose for tests)
        url = os.environ.get("DATABASE_URL", "postgresql://test:test@localhost:5432/test_gate")
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine with pgvector extension.

    Session-scoped: one DB per test session.
    """
    url = _get_test_db_url()
    engine = create_engine(url, echo=False)

    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        conn.commit()

    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()

    # Cleanup testcontainer if used
    container = getattr(_get_test_db_url, "_container", None)
    if container:
        container.stop()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Provide a transactional test session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Provide a fresh MockLLMClient with default responses."""
    return MockLLMClient(
        subject_responses=[
            SubjectClassification(
                classified_subject="operating_systems",
                confidence=0.95,
                reasoning="test fixture",
            ),
        ],
        tag_responses=[
            # Pass 1
            TopicTagResult(
                topic_id="os_cpu_scheduling",
                subtopic_id="os_sched_algos",
                difficulty="medium",
                confidence=0.90,
                reasoning="test pass 1",
            ),
            # Pass 2 (agrees)
            TopicTagResult(
                topic_id="os_cpu_scheduling",
                subtopic_id="os_sched_algos",
                difficulty="medium",
                confidence=0.88,
                reasoning="test pass 2",
            ),
        ],
    )


@pytest.fixture
def disagreeing_llm_client() -> MockLLMClient:
    """Provide a MockLLMClient where dual-pass tags disagree."""
    return MockLLMClient(
        subject_responses=[
            SubjectClassification(
                classified_subject="operating_systems",
                confidence=0.85,
                reasoning="test fixture",
            ),
        ],
        tag_responses=[
            # Pass 1
            TopicTagResult(
                topic_id="os_cpu_scheduling",
                subtopic_id="os_sched_algos",
                difficulty="medium",
                confidence=0.70,
                reasoning="pass 1 thinks scheduling",
            ),
            # Pass 2 (disagrees)
            TopicTagResult(
                topic_id="os_memory_management",
                subtopic_id="os_paging",
                difficulty="hard",
                confidence=0.65,
                reasoning="pass 2 thinks memory",
            ),
        ],
    )


@pytest.fixture
def sample_taxonomy() -> dict:
    """Provide a minimal taxonomy for testing."""
    return {
        "subject": {
            "id": "operating_systems",
            "name": "Operating Systems",
            "code": "CS-OS",
            "topics": [
                {
                    "id": "os_cpu_scheduling",
                    "name": "CPU Scheduling",
                    "code": "OS-CS",
                    "subtopics": [
                        {
                            "id": "os_sched_algos",
                            "name": "Scheduling Algorithms",
                            "code": "OS-CS-ALG",
                        },
                    ],
                },
                {
                    "id": "os_memory_management",
                    "name": "Memory Management",
                    "code": "OS-MM",
                    "subtopics": [
                        {
                            "id": "os_paging",
                            "name": "Paging",
                            "code": "OS-MM-PG",
                        },
                    ],
                },
            ],
        },
    }


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


def make_question_id() -> str:
    """Generate a unique question ID for tests."""
    return str(uuid.uuid4())
