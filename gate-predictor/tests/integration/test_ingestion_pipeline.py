"""Integration test for the full ingestion pipeline.

Requires a real PostgreSQL database with pgvector (via testcontainers).
"""

from __future__ import annotations

import uuid

import pytest

from app.core.llm_client import MockLLMClient, SubjectClassification
from app.db.models.question import ParseStatus, Question, QuestionSource, QuestionType, TagStatus
from app.db.models.subject import Subject
from app.ingestion.dedup import DuplicateChecker
from app.tagging.taxonomy import seed_all_subjects, seed_taxonomy


@pytest.mark.integration
class TestIngestionPipeline:
    """End-to-end tests for the ingestion and dedup pipeline."""

    def test_question_insert_with_provenance(self, db_session) -> None:
        """A question can be inserted with full provenance and queried back."""
        seed_all_subjects(db_session)
        db_session.flush()

        q = Question(
            id=str(uuid.uuid4()),
            subject_id="operating_systems",
            classified_subject="operating_systems",
            year=2023,
            set_no=1,
            question_no=1,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="What scheduling algorithm gives minimum average waiting time?",
            options={"A": "FCFS", "B": "SJF", "C": "RR", "D": "Priority"},
            answer={"correct": ["B"]},
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.UNTAGGED,
            text_hash="abc123unique",
            provenance={
                "raw_file": "GATE_CS_2023_Set1.pdf",
                "page": 5,
                "extraction_method": "pymupdf",
                "confidence": 0.95,
            },
        )
        db_session.add(q)
        db_session.flush()

        loaded = db_session.get(Question, q.id)
        assert loaded is not None
        assert loaded.year == 2023
        assert loaded.provenance["raw_file"] == "GATE_CS_2023_Set1.pdf"
        assert loaded.provenance["page"] == 5
        assert loaded.classified_subject == "operating_systems"

    def test_unique_constraint_prevents_duplicate(self, db_session) -> None:
        """UNIQUE(subject_id, year, set_no, question_no) prevents re-insertion."""
        seed_all_subjects(db_session)
        db_session.flush()

        shared_args = dict(
            subject_id="operating_systems",
            classified_subject="operating_systems",
            year=2023,
            set_no=1,
            question_no=42,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="Test",
            answer={"correct": ["A"]},
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.UNTAGGED,
            text_hash="hash42",
        )

        q1 = Question(id=str(uuid.uuid4()), **shared_args)
        db_session.add(q1)
        db_session.flush()

        from sqlalchemy.exc import IntegrityError

        q2 = Question(id=str(uuid.uuid4()), **shared_args)
        db_session.add(q2)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_text_hash_dedup(self, db_session) -> None:
        """DuplicateChecker detects same text_hash."""
        seed_all_subjects(db_session)
        db_session.flush()

        q = Question(
            id=str(uuid.uuid4()),
            subject_id="operating_systems",
            classified_subject="operating_systems",
            year=2022,
            set_no=1,
            question_no=1,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="Dedup test",
            answer={"correct": ["C"]},
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.UNTAGGED,
            text_hash="dedup_hash_test",
        )
        db_session.add(q)
        db_session.flush()

        checker = DuplicateChecker(db_session)
        assert checker.check_text_hash("dedup_hash_test") is True
        assert checker.check_text_hash("unique_hash") is False

    def test_nullable_topic_for_non_target_subject(self, db_session) -> None:
        """Non-target-subject questions have nullable topic_id and subtopic_id."""
        seed_all_subjects(db_session)
        db_session.flush()

        q = Question(
            id=str(uuid.uuid4()),
            subject_id="data_structures",
            classified_subject="data_structures",
            year=2023,
            set_no=1,
            question_no=10,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="What is the time complexity of inserting into a BST?",
            answer={"correct": ["B"]},
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.UNTAGGED,
            text_hash="ds_question_hash",
            topic_id=None,
            subtopic_id=None,
        )
        db_session.add(q)
        db_session.flush()

        loaded = db_session.get(Question, q.id)
        assert loaded is not None
        assert loaded.topic_id is None
        assert loaded.classified_subject == "data_structures"

    def test_mta_answer_storage(self, db_session) -> None:
        """MTA (marks to all) answers store correctly as JSONB."""
        seed_all_subjects(db_session)
        db_session.flush()

        q = Question(
            id=str(uuid.uuid4()),
            subject_id="operating_systems",
            classified_subject="operating_systems",
            year=2021,
            set_no=1,
            question_no=15,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="Controversial question",
            answer={"mta": True},
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.UNTAGGED,
            text_hash="mta_hash",
        )
        db_session.add(q)
        db_session.flush()

        loaded = db_session.get(Question, q.id)
        assert loaded is not None
        assert loaded.answer["mta"] is True
