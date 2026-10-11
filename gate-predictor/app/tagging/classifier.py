"""Dual-pass LLM topic/subtopic/difficulty tagger.

Key design decisions:
- Tags each question TWICE with independent LLM calls
- If both passes agree → tag_status = "suggested"
- If they disagree → tag_status = "disagreement" (goes to review queue)
- "verified" status is ONLY set via human CSV import, never by the LLM
- Supports "out_of_scope" topic for questions that don't fit the taxonomy
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.llm_client import LLMClient, TopicTagResult
from app.core.logging import get_logger
from app.db.models.question import Question, TagStatus

logger = get_logger(__name__)


@dataclass
class DualTagResult:
    """Result of dual-pass tagging for a single question."""

    question_id: str
    pass_1: TopicTagResult
    pass_2: TopicTagResult
    agreed: bool
    final_topic_id: str | None
    final_subtopic_id: str | None
    final_difficulty: str
    tag_status: str  # "suggested" | "disagreement"


class DualPassTagger:
    """Tags questions with topic/subtopic/difficulty using two independent LLM calls.

    Args:
        llm_client: LLMClient for tagging calls.
        taxonomy_tree: The taxonomy tree dict for the target subject.
        subject_id: The target subject ID.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        taxonomy_tree: dict[str, Any],
        subject_id: str,
    ) -> None:
        self._llm_client = llm_client
        self._taxonomy = taxonomy_tree
        self._subject_id = subject_id

    def tag_question(
        self,
        question_text: str,
        options: dict[str, str] | None,
        question_id: str,
    ) -> DualTagResult:
        """Tag a single question with two independent LLM calls.

        Args:
            question_text: The full question text.
            options: Option dict if MCQ/MSQ, None for NAT.
            question_id: The question's database ID.

        Returns:
            A DualTagResult with both passes and agreement status.
        """
        # Pass 1
        pass_1 = self._llm_client.tag_question(
            question_text=question_text,
            options=options,
            taxonomy=self._taxonomy,
            subject_id=self._subject_id,
        )

        # Pass 2 (independent call)
        pass_2 = self._llm_client.tag_question(
            question_text=question_text,
            options=options,
            taxonomy=self._taxonomy,
            subject_id=self._subject_id,
        )

        # Check agreement
        agreed = (
            pass_1.topic_id == pass_2.topic_id
            and pass_1.subtopic_id == pass_2.subtopic_id
            and pass_1.difficulty == pass_2.difficulty
        )

        if agreed:
            final_topic = pass_1.topic_id
            final_subtopic = pass_1.subtopic_id
            final_difficulty = pass_1.difficulty
            tag_status = TagStatus.SUGGESTED.value
        else:
            # Use pass_1 as provisional but flag disagreement
            final_topic = pass_1.topic_id
            final_subtopic = pass_1.subtopic_id
            final_difficulty = pass_1.difficulty
            tag_status = TagStatus.DISAGREEMENT.value
            logger.warning(
                "tag_disagreement",
                question_id=question_id,
                pass_1_topic=pass_1.topic_id,
                pass_2_topic=pass_2.topic_id,
                pass_1_difficulty=pass_1.difficulty,
                pass_2_difficulty=pass_2.difficulty,
            )

        # Handle out_of_scope
        if final_topic == "out_of_scope":
            final_topic = None
            final_subtopic = None

        return DualTagResult(
            question_id=question_id,
            pass_1=pass_1,
            pass_2=pass_2,
            agreed=agreed,
            final_topic_id=final_topic,
            final_subtopic_id=final_subtopic,
            final_difficulty=final_difficulty,
            tag_status=tag_status,
        )

    def apply_tags_to_db(self, session: Session, result: DualTagResult) -> None:
        """Apply dual-tag results to a question record in the database.

        Args:
            session: A SQLAlchemy session.
            result: The DualTagResult to apply.
        """
        question = session.get(Question, result.question_id)
        if question is None:
            logger.error("question_not_found", id=result.question_id)
            return

        question.topic_id = result.final_topic_id
        question.subtopic_id = result.final_subtopic_id
        question.difficulty = result.final_difficulty  # type: ignore[assignment]
        question.tag_status = result.tag_status  # type: ignore[assignment]

        # Store both passes as JSONB
        question.tag_pass_1 = {  # type: ignore[assignment]
            "topic_id": result.pass_1.topic_id,
            "subtopic_id": result.pass_1.subtopic_id,
            "difficulty": result.pass_1.difficulty,
            "confidence": result.pass_1.confidence,
            "reasoning": result.pass_1.reasoning,
        }
        question.tag_pass_2 = {  # type: ignore[assignment]
            "topic_id": result.pass_2.topic_id,
            "subtopic_id": result.pass_2.subtopic_id,
            "difficulty": result.pass_2.difficulty,
            "confidence": result.pass_2.confidence,
            "reasoning": result.pass_2.reasoning,
        }

        session.flush()

        logger.info(
            "tags_applied",
            question_id=result.question_id,
            topic=result.final_topic_id,
            subtopic=result.final_subtopic_id,
            difficulty=result.final_difficulty,
            status=result.tag_status,
            agreed=result.agreed,
        )


def tag_batch(
    session: Session,
    llm_client: LLMClient,
    taxonomy_tree: dict[str, Any],
    subject_id: str,
    questions: list[Question],
) -> list[DualTagResult]:
    """Tag a batch of questions using dual-pass tagging.

    Only tags questions that are classified as the target subject
    and have parse_status="parsed".

    Args:
        session: A SQLAlchemy session.
        llm_client: LLMClient for tagging.
        taxonomy_tree: The taxonomy tree for the target subject.
        subject_id: The target subject ID.
        questions: List of Question objects to tag.

    Returns:
        List of DualTagResult objects.
    """
    tagger = DualPassTagger(
        llm_client=llm_client,
        taxonomy_tree=taxonomy_tree,
        subject_id=subject_id,
    )

    results: list[DualTagResult] = []
    for question in questions:
        # Only tag questions classified as the target subject
        if question.classified_subject != subject_id:
            logger.debug(
                "skipping_non_target",
                question_id=question.id,
                classified=question.classified_subject,
            )
            continue

        result = tagger.tag_question(
            question_text=question.text,
            options=question.options,
            question_id=question.id,
        )
        tagger.apply_tags_to_db(session, result)
        results.append(result)

    logger.info(
        "batch_tagged",
        total=len(questions),
        tagged=len(results),
        agreed=sum(1 for r in results if r.agreed),
        disagreements=sum(1 for r in results if not r.agreed),
    )

    return results
