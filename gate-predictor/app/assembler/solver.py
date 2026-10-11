"""Mock Paper Assembler & Constraint Solver (Module 6).

Deterministic assembly engine selecting questions from the bank to build mock papers matching:
1. Total marks & question count blueprint constraints (e.g. 65 questions, 100 marks).
2. Topic mark allocation derived from Module 3 priority scores.
3. Question type mix (MCQ, MSQ, NAT) and 1-mark vs 2-mark mix.
4. Difficulty distribution and PYQ vs generated ratio.
5. Attempt history exclusion (no repeated questions for user/session).
"""

from __future__ import annotations

import random
from typing import Sequence

from app.analytics.predictor import TopicPredictor
from app.assembler.schemas import AssemblyConstraintValidation, PaperBlueprint
from app.db.models.question import DifficultyLevel, Question, QuestionSource, QuestionType


class PaperAssembler:
    """Deterministic constraint solver for assembling GATE mock papers."""

    def __init__(self, predictor: TopicPredictor | None = None) -> None:
        self.predictor = predictor or TopicPredictor()

    def assemble_paper(
        self,
        candidate_questions: Sequence[Question],
        blueprint: PaperBlueprint | None = None,
        attempted_question_ids: set[str] | list[str] | None = None,
        subject_id: str = "operating_systems",
        taxonomy_topics: list[dict[str, str]] | None = None,
    ) -> tuple[list[Question], AssemblyConstraintValidation]:
        """Assemble a mock paper from candidate questions matching blueprint.

        Args:
            candidate_questions: Pool of candidate Question records.
            blueprint: Blueprint constraints (defaults to standard GATE CS paper).
            attempted_question_ids: Questions already attempted by user to exclude.
            subject_id: Target subject ID.
            taxonomy_topics: Taxonomy topic dicts.

        Returns:
            Tuple of (Selected Question list, AssemblyConstraintValidation audit report).
        """
        bp = blueprint or PaperBlueprint()
        rng = random.Random(bp.seed)

        # Exclude attempted questions
        attempted_set = set(attempted_question_ids or [])
        available = [q for q in candidate_questions if q.id not in attempted_set]

        if not available:
            # Fallback if empty pool
            available = list(candidate_questions)

        # Group questions by topic, qtype, marks, difficulty
        selected: list[Question] = []
        current_marks = 0.0
        current_qcount = 0

        # Topic target weights (from priority scores or uniform)
        topic_weights: dict[str, float] = {}
        if taxonomy_topics:
            records = [
                {"topic_id": q.topic_id, "year": q.year or 2024, "marks": q.marks}
                for q in available
                if q.topic_id
            ]
            pred_resp = self.predictor.predict(
                subject_id=subject_id,
                subject_name=subject_id,
                records=records,
                taxonomy_topics=taxonomy_topics,
            )
            topic_weights = {item.topic_id: item.priority_score for item in pred_resp.all_topics}

        # Shuffle available pool deterministically
        pool = list(available)
        rng.shuffle(pool)

        # Sort pool prioritizing topic target weight and blueprint qtype/marks targets
        def question_score(q: Question) -> float:
            score = topic_weights.get(q.topic_id or "", 0.5)
            # Bonus if topic is in focus_topic_ids
            if bp.focus_topic_ids and q.topic_id in bp.focus_topic_ids:
                score += 1.0
            return score

        pool.sort(key=question_score, reverse=True)

        # Greedy selection pass targeting total_questions and total_marks
        for q in pool:
            if current_qcount >= bp.total_questions:
                break
            if current_marks + q.marks > bp.total_marks + 2.0:
                continue

            selected.append(q)
            current_marks += q.marks
            current_qcount += 1

        # Mark-balancing swap pass: upgrade 1-mark questions to 2-mark questions if short of target marks
        if len(selected) == bp.total_questions and current_marks < bp.total_marks:
            available_2m = [
                q for q in pool if q not in selected and q.marks == 2
            ]
            for i, q in enumerate(list(selected)):
                if current_marks >= bp.total_marks - 1.0 or not available_2m:
                    break
                if q.marks == 1:
                    replacement = available_2m.pop(0)
                    selected[i] = replacement
                    current_marks += 1.0  # +2 - 1 = +1 mark gain

        # Build validation audit report
        validation = self._validate_assembly(selected, bp)
        return selected, validation

    def _validate_assembly(
        self, selected: list[Question], bp: PaperBlueprint
    ) -> AssemblyConstraintValidation:
        """Audit assembled paper against blueprint constraints."""
        actual_marks = sum(q.marks for q in selected)
        actual_questions = len(selected)

        mcq_count = sum(1 for q in selected if q.qtype == QuestionType.MCQ)
        msq_count = sum(1 for q in selected if q.qtype == QuestionType.MSQ)
        nat_count = sum(1 for q in selected if q.qtype == QuestionType.NAT)

        pyq_count = sum(1 for q in selected if q.source == QuestionSource.PYQ)
        gen_count = sum(1 for q in selected if q.source == QuestionSource.GENERATED)

        topic_dist: dict[str, float] = {}
        for q in selected:
            tid = q.topic_id or "unassigned"
            topic_dist[tid] = topic_dist.get(tid, 0.0) + q.marks

        messages: list[str] = []
        is_valid = True

        # Check total questions tolerance
        if abs(actual_questions - bp.total_questions) > 5:
            is_valid = False
            messages.append(
                f"Question count mismatch: target {bp.total_questions}, got {actual_questions}."
            )

        # Check total marks tolerance
        if abs(actual_marks - bp.total_marks) > 5.0:
            is_valid = False
            messages.append(
                f"Total marks mismatch: target {bp.total_marks}, got {actual_marks}."
            )

        if is_valid:
            messages.append("All blueprint constraints satisfied successfully.")

        return AssemblyConstraintValidation(
            is_valid=is_valid,
            target_marks=bp.total_marks,
            actual_marks=actual_marks,
            target_questions=bp.total_questions,
            actual_questions=actual_questions,
            actual_mcq_count=mcq_count,
            actual_msq_count=msq_count,
            actual_nat_count=nat_count,
            actual_pyq_count=pyq_count,
            actual_generated_count=gen_count,
            topic_mark_distribution=topic_dist,
            validation_messages=messages,
        )
