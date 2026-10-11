"""Tests for dual-pass tagging and review queue.

Covers:
- Dual tagging agreement and disagreement
- out_of_scope handling
- Review queue CSV export and import
- Verified status only via human import
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path

import pytest

from app.core.llm_client import MockLLMClient, TopicTagResult
from app.db.models.question import ParseStatus, Question, QuestionSource, QuestionType, TagStatus
from app.tagging.classifier import DualPassTagger
from app.tagging.review_queue import export_review_queue, import_review_decisions
from app.tagging.taxonomy import get_taxonomy_tree


class TestDualPassTagger:
    """Tests for dual-pass LLM topic tagging."""

    def test_agreement_yields_suggested(self, mock_llm_client, sample_taxonomy) -> None:
        """When both passes agree, tag_status should be 'suggested'."""
        tree = get_taxonomy_tree(sample_taxonomy)
        tagger = DualPassTagger(
            llm_client=mock_llm_client,
            taxonomy_tree=tree,
            subject_id="operating_systems",
        )

        result = tagger.tag_question(
            question_text="What is Round Robin scheduling?",
            options={"A": "FCFS", "B": "SJF", "C": "RR", "D": "Priority"},
            question_id="test-q-1",
        )

        assert result.agreed is True
        assert result.tag_status == "suggested"
        assert result.final_topic_id == "os_cpu_scheduling"
        assert result.final_subtopic_id == "os_sched_algos"

    def test_disagreement_yields_disagreement(self, disagreeing_llm_client, sample_taxonomy) -> None:
        """When passes disagree, tag_status should be 'disagreement'."""
        tree = get_taxonomy_tree(sample_taxonomy)
        tagger = DualPassTagger(
            llm_client=disagreeing_llm_client,
            taxonomy_tree=tree,
            subject_id="operating_systems",
        )

        result = tagger.tag_question(
            question_text="Ambiguous question about OS",
            options=None,
            question_id="test-q-2",
        )

        assert result.agreed is False
        assert result.tag_status == "disagreement"

    def test_out_of_scope_nulls_topic(self, sample_taxonomy) -> None:
        """out_of_scope topic should result in None topic_id."""
        client = MockLLMClient(
            tag_responses=[
                TopicTagResult("out_of_scope", None, "medium", 0.80, "not in taxonomy"),
                TopicTagResult("out_of_scope", None, "medium", 0.85, "not in taxonomy"),
            ]
        )
        tree = get_taxonomy_tree(sample_taxonomy)
        tagger = DualPassTagger(client, tree, "operating_systems")

        result = tagger.tag_question("Random question", None, "test-q-3")

        assert result.final_topic_id is None
        assert result.final_subtopic_id is None
        assert result.agreed is True

    def test_llm_called_twice(self, sample_taxonomy) -> None:
        """Verify the LLM is called exactly twice (dual pass)."""
        client = MockLLMClient()
        tree = get_taxonomy_tree(sample_taxonomy)
        tagger = DualPassTagger(client, tree, "operating_systems")

        tagger.tag_question("Test", None, "test-q-4")

        tag_calls = [c for c in client.call_log if c["method"] == "tag_question"]
        assert len(tag_calls) == 2


@pytest.mark.integration
class TestReviewQueue:
    """Integration tests for review queue CSV export/import."""

    def _make_question(self, session, tag_status: TagStatus, q_no: int = 1) -> Question:
        """Helper to create a test question in the DB."""
        from app.tagging.taxonomy import seed_all_subjects

        seed_all_subjects(session)
        session.flush()

        q = Question(
            id=str(uuid.uuid4()),
            subject_id="operating_systems",
            classified_subject="operating_systems",
            year=2023,
            set_no=1,
            question_no=q_no,
            source=QuestionSource.PYQ,
            qtype=QuestionType.MCQ,
            marks=1,
            text="Test question for review",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer={"correct": ["A"]},
            parse_status=ParseStatus.PARSED,
            tag_status=tag_status,
            text_hash="abc123" + str(q_no),
            topic_id=None,
        )
        session.add(q)
        session.flush()
        return q

    def test_export_includes_suggested_and_disagreement(self, db_session, tmp_path) -> None:
        """Export should include both suggested and disagreement questions."""
        q1 = self._make_question(db_session, TagStatus.SUGGESTED, q_no=1)
        q2 = self._make_question(db_session, TagStatus.DISAGREEMENT, q_no=2)

        csv_path = tmp_path / "review.csv"
        count = export_review_queue(db_session, csv_path)

        assert count == 2
        assert csv_path.exists()

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        ids = {row["question_id"] for row in rows}
        assert q1.id in ids
        assert q2.id in ids

    def test_import_verify_sets_verified_status(self, db_session, tmp_path) -> None:
        """Importing with action='verify' should set tag_status to VERIFIED."""
        q = self._make_question(db_session, TagStatus.SUGGESTED)

        csv_path = tmp_path / "reviewed.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "question_id", "action", "corrected_topic", "corrected_subtopic",
                "corrected_difficulty", "notes",
            ])
            writer.writeheader()
            writer.writerow({
                "question_id": q.id,
                "action": "verify",
                "corrected_topic": "",
                "corrected_subtopic": "",
                "corrected_difficulty": "",
                "notes": "",
            })

        counts = import_review_decisions(db_session, csv_path)
        assert counts["verified"] == 1

        db_session.refresh(q)
        assert q.tag_status == TagStatus.VERIFIED

    def test_import_reject(self, db_session, tmp_path) -> None:
        """Importing with action='reject' should set tag_status to REJECTED."""
        q = self._make_question(db_session, TagStatus.DISAGREEMENT)

        csv_path = tmp_path / "reviewed.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["question_id", "action"])
            writer.writeheader()
            writer.writerow({"question_id": q.id, "action": "reject"})

        counts = import_review_decisions(db_session, csv_path)
        assert counts["rejected"] == 1

        db_session.refresh(q)
        assert q.tag_status == TagStatus.REJECTED

    def test_import_with_corrections(self, db_session, tmp_path) -> None:
        """Corrected values should override proposed tags."""
        q = self._make_question(db_session, TagStatus.DISAGREEMENT)

        csv_path = tmp_path / "reviewed.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "question_id", "action", "corrected_topic", "corrected_subtopic",
                "corrected_difficulty", "notes",
            ])
            writer.writeheader()
            writer.writerow({
                "question_id": q.id,
                "action": "verify",
                "corrected_topic": "os_memory_management",
                "corrected_subtopic": "os_paging",
                "corrected_difficulty": "hard",
                "notes": "Actually about virtual memory",
            })

        import_review_decisions(db_session, csv_path)

        db_session.refresh(q)
        assert q.tag_status == TagStatus.VERIFIED
        assert q.topic_id == "os_memory_management"
        assert q.subtopic_id == "os_paging"
        assert q.difficulty.value == "hard"
        assert q.verification_metadata.get("human_review", {}).get("notes") == "Actually about virtual memory"
