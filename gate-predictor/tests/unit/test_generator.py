"""Unit tests for Question Generator pipeline (Module 5)."""

from __future__ import annotations

import pytest

from app.db.models.question import DifficultyLevel, QuestionType
from app.generation.generator import QuestionGenerator
from app.core.llm_client import MockLLMClient


class TestQuestionGenerator:
    def test_generate_question_mcq_success(self):
        llm_client = MockLLMClient()
        generator = QuestionGenerator(llm_client=llm_client)

        question, verif = generator.generate_question(
            topic_id="os_process_mgmt",
            topic_name="Process Management",
            difficulty=DifficultyLevel.MEDIUM,
            qtype=QuestionType.MCQ,
            marks=1,
        )

        assert question is not None
        assert verif.passed is True
        assert question.source.value == "generated"
        assert question.topic_id == "os_process_mgmt"
        assert question.qtype == QuestionType.MCQ
        assert question.text_hash is not None

    def test_generate_question_nat_success(self):
        llm_client = MockLLMClient()
        generator = QuestionGenerator(llm_client=llm_client)

        question, verif = generator.generate_question(
            topic_id="os_memory_mgmt",
            topic_name="Memory Management",
            difficulty=DifficultyLevel.EASY,
            qtype=QuestionType.NAT,
            marks=2,
        )

        assert question is not None
        assert verif.passed is True
        assert question.qtype == QuestionType.NAT
        assert question.marks == 2

    def test_retry_on_dedup_failure(self):
        llm_client = MockLLMClient()
        generator = QuestionGenerator(llm_client=llm_client, max_retries=1)

        # Mock existing bank text to force near-duplicate failure
        duplicate_text = (
            "What is the average waiting time for 3 processes with burst times 10, 5, and 8 under FCFS scheduling?"
        )

        question, verif = generator.generate_question(
            topic_id="os_process_mgmt",
            topic_name="Process Management",
            difficulty=DifficultyLevel.MEDIUM,
            qtype=QuestionType.MCQ,
            marks=1,
            existing_bank_texts=[duplicate_text],
        )

        # Verification should fail near duplicate check
        assert verif.step_results["near_duplicate_check"] is False
