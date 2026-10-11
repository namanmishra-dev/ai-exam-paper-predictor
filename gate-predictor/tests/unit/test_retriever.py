"""Unit tests for RAG Retriever (Module 5)."""

from __future__ import annotations

import pytest

from app.db.models.question import DifficultyLevel
from app.generation.retriever import QuestionRetriever


class TestQuestionRetriever:
    def test_retrieve_reference_pyqs_fallback(self):
        retriever = QuestionRetriever()
        pyqs = retriever.retrieve_reference_pyqs(
            topic_id="os_process_mgmt",
            difficulty=DifficultyLevel.MEDIUM,
            limit=3,
        )

        assert len(pyqs) == 3
        for q in pyqs:
            assert q.topic_id == "os_process_mgmt"
            assert q.source.value == "pyq"

    def test_cosine_similarity(self):
        retriever = QuestionRetriever()

        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]

        assert pytest.approx(retriever.compute_cosine_similarity(v1, v2), 0.001) == 1.0
        assert pytest.approx(retriever.compute_cosine_similarity(v1, v3), 0.001) == 0.0
