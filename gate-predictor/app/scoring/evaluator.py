"""Scoring Engine (Module 7).

Evaluates user mock paper submissions according to official GATE rules:
- 1-mark MCQ: +1.0 correct, -1/3 (-0.3333) wrong, 0 unattempted
- 2-mark MCQ: +2.0 correct, -2/3 (-0.6667) wrong, 0 unattempted
- MSQ: +marks exact option set match, 0 wrong (no negative marking, no partial credit)
- NAT: +marks if numeric value in [min, max], 0 wrong (no negative marking)
- MTA: +marks allocated for all attempts

Computes topic-wise accuracy and flags weak topics linked back to Module 3 priorities.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.db.models.question import Question, QuestionType
from app.scoring.schemas import (
    AttemptScoreReport,
    QuestionAnswerPayload,
    QuestionScoreDetail,
    SubmitAttemptRequest,
    TopicAccuracy,
)


class ScoringEngine:
    """Evaluates question responses and computes detailed attempt score reports."""

    def evaluate_attempt(
        self,
        submission: SubmitAttemptRequest,
        paper_questions: Sequence[Question],
        topic_priority_buckets: dict[str, str] | None = None,
        topic_names: dict[str, str] | None = None,
    ) -> AttemptScoreReport:
        """Evaluate submission against paper questions and return score report.

        Args:
            submission: SubmitAttemptRequest object containing user answers.
            paper_questions: List of Question objects in the paper.
            topic_priority_buckets: Dict mapping topic_id -> PriorityBucket string.
            topic_names: Dict mapping topic_id -> topic display name.

        Returns:
            AttemptScoreReport detailing scores, accuracy, and topic analytics.
        """
        priority_map = topic_priority_buckets or {}
        name_map = topic_names or {}

        # Map submission answers by question_id
        user_answer_map: dict[str, QuestionAnswerPayload] = {
            ans.question_id: ans for ans in submission.answers
        }

        question_details: list[QuestionScoreDetail] = []
        topic_stats: dict[str, dict[str, Any]] = {}

        total_score = 0.0
        max_score = sum(q.marks for q in paper_questions)
        correct_count = 0
        incorrect_count = 0
        unattempted_count = 0
        total_time = 0.0

        for q in paper_questions:
            payload = user_answer_map.get(q.id)
            user_ans = payload.user_answer if payload else None
            time_sec = payload.time_taken_seconds if payload else 0.0
            total_time += time_sec

            # Evaluate question
            marks_obtained, is_correct, is_unattempted = self._score_question(q, user_ans)
            total_score += marks_obtained

            if is_unattempted:
                unattempted_count += 1
            elif is_correct:
                correct_count += 1
            else:
                incorrect_count += 1

            # Detail record
            detail = QuestionScoreDetail(
                question_id=q.id,
                qtype=q.qtype.value,
                marks_allocated=q.marks,
                marks_obtained=round(marks_obtained, 4),
                is_correct=is_correct,
                user_answer=user_ans,
                correct_answer=q.answer,
                explanation=q.solution_text or "No solution provided.",
                topic_id=q.topic_id,
            )
            question_details.append(detail)

            # Aggregate per-topic statistics
            tid = q.topic_id or "unassigned"
            if tid not in topic_stats:
                topic_stats[tid] = {
                    "total_questions": 0,
                    "correct_count": 0,
                    "marks_allocated": 0.0,
                    "marks_obtained": 0.0,
                }
            t = topic_stats[tid]
            t["total_questions"] += 1
            if is_correct:
                t["correct_count"] += 1
            t["marks_allocated"] += q.marks
            t["marks_obtained"] += marks_obtained

        # Compute topic analytics
        topic_analytics: list[TopicAccuracy] = []
        for tid, t in topic_stats.items():
            acc_pct = (
                (t["marks_obtained"] / t["marks_allocated"] * 100.0)
                if t["marks_allocated"] > 0
                else 0.0
            )
            acc = TopicAccuracy(
                topic_id=tid,
                topic_name=name_map.get(tid, tid),
                total_questions=t["total_questions"],
                correct_count=t["correct_count"],
                marks_allocated=t["marks_allocated"],
                marks_obtained=round(t["marks_obtained"], 4),
                accuracy_pct=round(max(0.0, acc_pct), 2),
                priority_bucket=priority_map.get(tid, "MUST_DO"),
            )
            topic_analytics.append(acc)

        # Identify weak topics (accuracy < 60% or Must-Do topics with low score)
        weak_topics = [
            t for t in topic_analytics if t.accuracy_pct < 60.0 or t.priority_bucket == "MUST_DO" and t.accuracy_pct < 75.0
        ]
        weak_topics.sort(key=lambda t: t.accuracy_pct)

        overall_accuracy = (total_score / max_score * 100.0) if max_score > 0 else 0.0

        return AttemptScoreReport(
            attempt_id=submission.attempt_id or "attempt_preview",
            mock_paper_id=submission.mock_paper_id,
            total_score=round(max(0.0, total_score), 4),
            max_score=round(max_score, 4),
            accuracy_pct=round(max(0.0, overall_accuracy), 2),
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unattempted_count=unattempted_count,
            total_time_seconds=round(total_time, 2),
            question_details=question_details,
            topic_analytics=topic_analytics,
            weak_topics=weak_topics,
        )

    def _score_question(self, q: Question, user_ans: Any) -> tuple[float, bool, bool]:
        """Score a single question according to GATE negative marking rules.

        Returns:
            Tuple of (marks_obtained, is_correct, is_unattempted).
        """
        # Unattempted case
        if user_ans is None or user_ans == "" or user_ans == []:
            # Check for MTA (Marks To All)
            if isinstance(q.answer, dict) and q.answer.get("mta"):
                return float(q.marks), True, False
            return 0.0, False, True

        # Check for MTA
        if isinstance(q.answer, dict) and q.answer.get("mta"):
            return float(q.marks), True, False

        if q.qtype == QuestionType.MCQ:
            # Answer is dict with key "keys" e.g. {"keys": ["A"]} or direct list ["A"]
            correct_keys = self._extract_answer_keys(q.answer)
            user_key = (
                str(user_ans[0]).strip().upper()
                if isinstance(user_ans, list) and len(user_ans) > 0
                else str(user_ans).strip().upper()
            )

            if correct_keys and user_key == correct_keys[0]:
                return float(q.marks), True, False
            else:
                # MCQ Negative marking: 1/3 for 1-mark, 2/3 for 2-mark
                neg_penalty = (1.0 / 3.0) if q.marks == 1 else (2.0 / 3.0)
                return -neg_penalty, False, False

        elif q.qtype == QuestionType.MSQ:
            correct_keys = set(self._extract_answer_keys(q.answer))
            user_keys = (
                set(str(k).strip().upper() for k in user_ans)
                if isinstance(user_ans, list)
                else {str(user_ans).strip().upper()}
            )

            if user_keys == correct_keys and len(user_keys) > 0:
                return float(q.marks), True, False
            else:
                # MSQ: no negative marking, no partial credit
                return 0.0, False, False

        elif q.qtype == QuestionType.NAT:
            try:
                user_val = float(user_ans)
                ans_dict = q.answer if isinstance(q.answer, dict) else {}
                val = ans_dict.get("value")
                min_v = float(ans_dict.get("min", val if val is not None else user_val))
                max_v = float(ans_dict.get("max", val if val is not None else user_val))

                if min_v <= user_val <= max_v:
                    return float(q.marks), True, False
                else:
                    # NAT: no negative marking
                    return 0.0, False, False
            except (ValueError, TypeError):
                return 0.0, False, False

        return 0.0, False, False

    def _extract_answer_keys(self, answer_obj: Any) -> list[str]:
        """Extract option keys from answer JSON object."""
        if isinstance(answer_obj, list):
            return [str(k).strip().upper() for k in answer_obj]
        if isinstance(answer_obj, dict):
            if "keys" in answer_obj:
                return [str(k).strip().upper() for k in answer_obj["keys"]]
            if "value" in answer_obj:
                return [str(answer_obj["value"]).strip().upper()]
        return []
