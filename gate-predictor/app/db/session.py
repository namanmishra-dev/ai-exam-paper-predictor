"""SQLAlchemy session factory with connection pooling.

Provides a sync ``SessionLocal`` factory and a context-manager ``get_session``
for use in scripts and API endpoints.

Engine creation is deferred to avoid import-time DB connection attempts,
which would break test imports.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _ensure_psycopg2_url(url: str) -> str:
    """Ensure the DB URL uses the psycopg2 driver explicitly.

    SQLAlchemy 2.1+ defaults to psycopg (v3). We use psycopg2-binary,
    so the URL must specify ``postgresql+psycopg2://``.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine (lazily created)."""
    url = _ensure_psycopg2_url(settings.db.database_url)
    return create_engine(
        url,
        pool_size=settings.db.database_pool_size,
        max_overflow=settings.db.database_max_overflow,
        pool_pre_ping=True,
        echo=False,
    )


# Keep `engine` as a lazy property for backward compat
class _EngineProxy:
    """Lazy proxy so ``from app.db.session import engine`` doesn't connect at import time."""

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(get_engine(), name)


engine = _EngineProxy()  # type: ignore[assignment]


def _get_session_factory() -> sessionmaker[Session]:
    """Return a sessionmaker bound to the engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional database session.

    Commits on success, rolls back on exception, and always closes.

    Yields:
        A SQLAlchemy ``Session`` instance.
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    Yields:
        A SQLAlchemy ``Session`` instance.
    """
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

