"""Database models package.

Import all models here so Alembic's ``target_metadata`` can discover them.
"""

from app.db.models.subject import Subject, Topic, TopicPriority  # noqa: F401
from app.db.models.question import Question  # noqa: F401
from app.db.models.mock_paper import MockPaper, MockPaperQuestion  # noqa: F401
from app.db.models.attempt import Attempt, AttemptAnswer  # noqa: F401
from app.db.models.job import Job  # noqa: F401

__all__ = [
    "Subject",
    "Topic",
    "TopicPriority",
    "Question",
    "MockPaper",
    "MockPaperQuestion",
    "Attempt",
    "AttemptAnswer",
    "Job",
]
