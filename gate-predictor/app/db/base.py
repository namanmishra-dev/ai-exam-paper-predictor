"""SQLAlchemy 2.0 declarative base and shared metadata."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All models inherit from this class, which provides the shared
    ``MetaData`` and registry for Alembic auto-generation.
    """

    pass
