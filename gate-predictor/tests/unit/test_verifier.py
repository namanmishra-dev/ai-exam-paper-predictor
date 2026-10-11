"""Unit tests for the 5-step Verification Gate (Module 5)."""

from __future__ import annotations

import pytest

from app.db.models.question import DifficultyLevel, QuestionType
from app.generation.schemas import GeneratedQuestionDraft
from app.generation.verifier import QuestionVerifier


@pytest.fixture
def mcq_draft() -> GeneratedQuestionDraft:
    return GeneratedQuestionDraft(
        text="What is the time complexity of binary search on a sorted array of length $n$?",
        options={
            "A": "$O(\\log n)$",
            "B": "$O(n)$",
            "C": "$O(n \\log n)$",
            "D": "$O(1)$",
        },
        qtype=QuestionType.MCQ,
        marks=1,
        difficulty=DifficultyLevel.EASY,
        answer=["A"],
        solution_text="Binary search divides the search space in half at each step, yielding $O(\\log n)$.",
        topic_id="os_process_mgmt",
    )


@pytest.fixture
def msq_draft() -> GeneratedQuestionDraft:
    return GeneratedQuestionDraft(
        text="Which of the following process states are valid in a standard operating system kernel?",
        options={
            "A": "Running",
            "B": "Ready",
            "C": "Blocked / Waiting",
            "D": "Terminated",
        },
        qtype=QuestionType.MSQ,
        marks=2,
        difficulty=DifficultyLevel.MEDIUM,
        answer=["A", "B", "C", "D"],
        solution_text="All listed process states are standard states in OS state transition models.",
        topic_id="os_process_mgmt",
    )


@pytest.fixture
def nat_draft() -> GeneratedQuestionDraft:
    return GeneratedQuestionDraft(
        text="Calculate the throughput of a CPU processing 12 jobs in 4 seconds.",
        options=None,
        qtype=QuestionType.NAT,
        marks=2,
        difficulty=DifficultyLevel.EASY,
        answer={"value": 3.0, "min": 2.9, "max": 3.1},
        solution_text="Throughput = total jobs / total time = 12 / 4 = 3.0 jobs per second.",
        topic_id="os_process_mgmt",
    )


class TestQuestionVerifier:
    def test_schema_validation_mcq_success(self, mcq_draft):
        verifier = QuestionVerifier()
        res = verifier.verify_question(mcq_draft)
        assert res.step_results["schema_validation"] is True

    def test_schema_validation_mcq_invalid_options(self, mcq_draft):
        mcq_draft.options = {"A": "Opt A", "B": "Opt B"}  # Less than 4 options
        verifier = QuestionVerifier()
        res = verifier.verify_question(mcq_draft)
        assert res.passed is False
        assert res.step_results["schema_validation"] is False

    def test_nat_execution_check(self, nat_draft):
        verifier = QuestionVerifier()
        res = verifier.verify_question(nat_draft)
        assert res.step_results["nat_code_execution"] is True

    def test_nat_execution_check_out_of_bounds(self, nat_draft):
        nat_draft.answer = {"value": 10.0, "min": 2.0, "max": 4.0}  # Value out of range
        verifier = QuestionVerifier()
        res = verifier.verify_question(nat_draft)
        assert res.step_results["nat_code_execution"] is False

    def test_msq_set_equality(self, msq_draft):
        verifier = QuestionVerifier()
        # Test matching set
        res = verifier.verify_question(msq_draft)
        assert res.step_results["msq_exact_set_equality"] is True

    def test_near_duplicate_check_rejects_high_similarity(self, mcq_draft):
        verifier = QuestionVerifier(dedup_threshold=0.90)
        existing_texts = [mcq_draft.text]  # Exact duplicate text

        res = verifier.verify_question(mcq_draft, existing_bank_texts=existing_texts)
        assert res.passed is False
        assert res.step_results["near_duplicate_check"] is False
        assert res.similarity_score > 0.90
