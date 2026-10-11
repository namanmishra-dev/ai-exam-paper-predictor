"""Unit tests for Scoring Engine and GATE negative marking rules (Module 7)."""

from __future__ import annotations

import pytest

from app.db.models.question import DifficultyLevel, Question, QuestionSource, QuestionType
from app.scoring.evaluator import ScoringEngine
from app.scoring.schemas import QuestionAnswerPayload, SubmitAttemptRequest


@pytest.fixture
def mock_questions() -> list[Question]:
    q1 = Question(
        id="q1_mcq1",
        subject_id="operating_systems",
        classified_subject="operating_systems",
        topic_id="os_cpu_scheduling",
        qtype=QuestionType.MCQ,
        marks=1,
        text="MCQ 1-mark question",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        answer=["A"],
        text_hash="hash_q1",
    )
    q2 = Question(
        id="q2_mcq2",
        subject_id="operating_systems",
        classified_subject="operating_systems",
        topic_id="os_cpu_scheduling",
        qtype=QuestionType.MCQ,
        marks=2,
        text="MCQ 2-mark question",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        answer=["B"],
        text_hash="hash_q2",
    )
    q3 = Question(
        id="q3_msq",
        subject_id="operating_systems",
        classified_subject="operating_systems",
        topic_id="os_memory_mgmt",
        qtype=QuestionType.MSQ,
        marks=2,
        text="MSQ 2-mark question",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        answer=["A", "C"],
        text_hash="hash_q3",
    )
    q4 = Question(
        id="q4_nat",
        subject_id="operating_systems",
        classified_subject="operating_systems",
        topic_id="os_memory_mgmt",
        qtype=QuestionType.NAT,
        marks=2,
        text="NAT 2-mark question",
        options=None,
        answer={"value": 4.5, "min": 4.0, "max": 5.0},
        text_hash="hash_q4",
    )
    return [q1, q2, q3, q4]


class TestScoringEngine:
    def test_mcq_scoring(self, mock_questions):
        engine = ScoringEngine()

        # q1 correct (+1.0), q2 wrong (-0.6667)
        submission = SubmitAttemptRequest(
            mock_paper_id="paper_1",
            answers=[
                QuestionAnswerPayload(question_id="q1_mcq1", user_answer=["A"]),
                QuestionAnswerPayload(question_id="q2_mcq2", user_answer=["A"]),  # Wrong answer (correct is B)
            ],
        )

        report = engine.evaluate_attempt(submission, mock_questions)

        d1 = next(d for d in report.question_details if d.question_id == "q1_mcq1")
        d2 = next(d for d in report.question_details if d.question_id == "q2_mcq2")

        assert d1.marks_obtained == 1.0
        assert d1.is_correct is True
        assert pytest.approx(d2.marks_obtained, 0.01) == -2.0 / 3.0
        assert d2.is_correct is False

    def test_msq_scoring_no_negative_marking(self, mock_questions):
        engine = ScoringEngine()

        # q3 MSQ: correct ["A", "C"], wrong submission ["A"] (no partial credit, no penalty)
        submission = SubmitAttemptRequest(
            mock_paper_id="paper_1",
            answers=[
                QuestionAnswerPayload(question_id="q3_msq", user_answer=["A"]),
            ],
        )

        report = engine.evaluate_attempt(submission, mock_questions)

        d3 = next(d for d in report.question_details if d.question_id == "q3_msq")
        assert d3.marks_obtained == 0.0
        assert d3.is_correct is False

    def test_nat_scoring_within_range(self, mock_questions):
        engine = ScoringEngine()

        submission = SubmitAttemptRequest(
            mock_paper_id="paper_1",
            answers=[
                QuestionAnswerPayload(question_id="q4_nat", user_answer=4.2),  # In range [4.0, 5.0]
            ],
        )

        report = engine.evaluate_attempt(submission, mock_questions)

        d4 = next(d for d in report.question_details if d.question_id == "q4_nat")
        assert d4.marks_obtained == 2.0
        assert d4.is_correct is True

    def test_topic_analytics_and_weak_topics(self, mock_questions):
        engine = ScoringEngine()

        submission = SubmitAttemptRequest(
            mock_paper_id="paper_1",
            answers=[
                QuestionAnswerPayload(question_id="q1_mcq1", user_answer=["A"]),
                QuestionAnswerPayload(question_id="q2_mcq2", user_answer=["A"]),  # Wrong
            ],
        )

        report = engine.evaluate_attempt(submission, mock_questions)

        assert len(report.topic_analytics) > 0
        assert report.correct_count == 1
        assert report.incorrect_count == 1
        assert report.unattempted_count == 2
