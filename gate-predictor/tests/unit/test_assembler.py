"""Unit tests for Mock Paper Assembler (Module 6)."""

from __future__ import annotations

import pytest

from app.assembler.schemas import PaperBlueprint
from app.assembler.solver import PaperAssembler
from app.db.models.question import DifficultyLevel, Question, QuestionSource, QuestionType


@pytest.fixture
def question_pool() -> list[Question]:
    pool = []
    topics = ["os_process_mgmt", "os_memory_mgmt", "os_file_sys"]
    for i in range(1, 100):
        qtype = QuestionType.MCQ if i % 2 == 1 else (QuestionType.MSQ if i % 3 == 0 else QuestionType.NAT)
        q = Question(
            id=f"pool_q_{i}",
            subject_id="operating_systems",
            classified_subject="operating_systems",
            topic_id=topics[i % len(topics)],
            source=QuestionSource.PYQ if i % 2 == 0 else QuestionSource.GENERATED,
            year=2020 + (i % 5),
            qtype=qtype,
            marks=1 if i % 2 == 1 else 2,
            difficulty=DifficultyLevel.MEDIUM,
            text=f"Question pool item {i}",
            options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"} if qtype != QuestionType.NAT else None,
            answer=["A"] if qtype == QuestionType.MCQ else (["A", "B"] if qtype == QuestionType.MSQ else {"value": 5.0}),
            text_hash=f"hash_pool_{i}",
        )
        pool.append(q)
    return pool


class TestPaperAssembler:
    def test_assemble_full_gate_paper(self, question_pool):
        assembler = PaperAssembler()
        bp = PaperBlueprint(total_questions=65, total_marks=100.0, seed=42)

        selected, val = assembler.assemble_paper(question_pool, blueprint=bp)

        assert len(selected) == 65
        assert val.actual_questions == 65
        assert abs(val.actual_marks - 100.0) <= 5.0
        assert val.is_valid is True

    def test_assemble_mini_mock_paper(self, question_pool):
        assembler = PaperAssembler()
        bp = PaperBlueprint(total_questions=15, total_marks=25.0, seed=123)

        selected, val = assembler.assemble_paper(question_pool, blueprint=bp)

        assert len(selected) == 15
        assert val.actual_questions == 15
        assert abs(val.actual_marks - 25.0) <= 3.0

    def test_attempted_question_exclusion(self, question_pool):
        assembler = PaperAssembler()
        bp = PaperBlueprint(total_questions=10, total_marks=15.0, seed=42)

        attempted = {"pool_q_1", "pool_q_2", "pool_q_3"}
        selected, _ = assembler.assemble_paper(
            question_pool, blueprint=bp, attempted_question_ids=attempted
        )

        selected_ids = {q.id for q in selected}
        assert len(selected_ids.intersection(attempted)) == 0

    def test_reproducibility_with_seed(self, question_pool):
        assembler = PaperAssembler()
        bp1 = PaperBlueprint(total_questions=20, total_marks=30.0, seed=999)
        bp2 = PaperBlueprint(total_questions=20, total_marks=30.0, seed=999)

        sel1, _ = assembler.assemble_paper(question_pool, blueprint=bp1)
        sel2, _ = assembler.assemble_paper(question_pool, blueprint=bp2)

        assert [q.id for q in sel1] == [q.id for q in sel2]
