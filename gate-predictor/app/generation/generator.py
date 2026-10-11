"""Question Generator Pipeline (Module 5).

Combines RAG retrieval, LLM prompt execution, and the 5-step Verification Gate.
Supports retry logic (up to 2 retries on failure) before discarding or storing in bank.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.question import (
    DifficultyLevel,
    ParseStatus,
    Question,
    QuestionSource,
    QuestionType,
    TagStatus,
)
from app.generation.prompts.templates import (
    GENERATION_SYSTEM_PROMPT,
    GENERATION_USER_PROMPT_TEMPLATE,
)
from app.generation.retriever import QuestionRetriever
from app.generation.schemas import GeneratedQuestionDraft, VerificationResult
from app.generation.verifier import QuestionVerifier
from app.ingestion.cleaner import QuestionCleaner
from app.core.llm_client import LLMClient, get_llm_client

logger = get_logger(__name__)


class QuestionGenerator:
    """End-to-end question generator pipeline with RAG and Verification Gate."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        retriever: QuestionRetriever | None = None,
        verifier: QuestionVerifier | None = None,
        max_retries: int = 2,
    ) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.retriever = retriever or QuestionRetriever()
        self.verifier = verifier or QuestionVerifier(llm_client=self.llm_client)
        self.max_retries = max_retries

    def generate_question(
        self,
        topic_id: str,
        topic_name: str = "Operating Systems Topic",
        difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
        qtype: QuestionType = QuestionType.MCQ,
        marks: int = 1,
        session: Session | None = None,
        existing_bank_texts: list[str] | None = None,
    ) -> tuple[Question | None, VerificationResult]:
        """Generate and verify a new GATE question.

        Args:
            topic_id: Target topic ID.
            topic_name: Target topic display name.
            difficulty: Difficulty level.
            qtype: Question type (MCQ|MSQ|NAT).
            marks: Target marks (1 or 2).
            session: Optional SQLAlchemy session.
            existing_bank_texts: List of existing question texts for dedup.

        Returns:
            Tuple of (Question object or None if failed, VerificationResult).
        """
        # Step 1: RAG Retrieval of Reference PYQs
        ref_pyqs = self.retriever.retrieve_reference_pyqs(
            topic_id=topic_id,
            difficulty=difficulty,
            limit=3,
            session=session,
        )
        ref_text = "\n---\n".join([f"PYQ ({q.year}): {q.text}" for q in ref_pyqs])

        last_verification: VerificationResult | None = None

        # Retry loop (up to max_retries)
        for attempt in range(1 + self.max_retries):
            try:
                # Step 2: Build Prompt & Call LLM
                prompt = GENERATION_USER_PROMPT_TEMPLATE.format(
                    topic_name=topic_name,
                    topic_id=topic_id,
                    difficulty=difficulty.value,
                    qtype=qtype.value,
                    marks=marks,
                    reference_pyqs_text=ref_text,
                )

                raw_response = self.llm_client.complete(
                    prompt=prompt,
                    system=GENERATION_SYSTEM_PROMPT,
                )

                draft = self._parse_draft_json(raw_response)
                # Ensure draft fields match request parameters
                draft.topic_id = topic_id
                draft.difficulty = difficulty
                draft.qtype = qtype
                draft.marks = marks

                # Step 3: Run Verification Gate
                verif = self.verifier.verify_question(
                    draft=draft,
                    existing_bank_texts=existing_bank_texts,
                )
                last_verification = verif

                if verif.passed:
                    # Successfully verified! Build Question instance
                    question = self._create_question_model(draft, verif)

                    if session is not None:
                        session.add(question)
                        session.commit()

                    logger.info(
                        "question_generated_verified",
                        topic_id=topic_id,
                        qtype=qtype.value,
                        attempt=attempt + 1,
                    )
                    return question, verif

                logger.warning(
                    "verification_gate_failed",
                    topic_id=topic_id,
                    attempt=attempt + 1,
                    reasons=verif.failure_reasons,
                )
            except Exception as exc:
                logger.error("generation_attempt_error", attempt=attempt + 1, error=str(exc))

        if last_verification is None:
            last_verification = VerificationResult(
                passed=False,
                failure_reasons=["Generation failed across all attempts."],
            )

        return None, last_verification

    def _parse_draft_json(self, raw_text: str) -> GeneratedQuestionDraft:
        """Parse LLM JSON response into GeneratedQuestionDraft schema."""
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                raise ValueError(f"Could not extract JSON from generation response: {raw_text[:100]}...")

        return GeneratedQuestionDraft.model_validate(data)

    def _create_question_model(
        self, draft: GeneratedQuestionDraft, verif: VerificationResult
    ) -> Question:
        """Construct Question SQLAlchemy DB model from verified draft."""
        text_hash = QuestionCleaner.compute_text_hash(draft.text)
        q_id = f"gen_{uuid.uuid4().hex[:12]}"

        # Answer dict normalization
        if draft.qtype in (QuestionType.MCQ, QuestionType.MSQ):
            ans_dict = {"keys": draft.answer}
        else:
            ans_dict = draft.answer if isinstance(draft.answer, dict) else {"value": draft.answer}

        return Question(
            id=q_id,
            subject_id="operating_systems",
            classified_subject="operating_systems",
            topic_id=draft.topic_id,
            subtopic_id=draft.subtopic_id,
            source=QuestionSource.GENERATED,
            year=None,
            set_no=None,
            question_no=None,
            provenance={"generator": "AnthropicLLMClient", "prompt_version": "v1.0"},
            qtype=draft.qtype,
            marks=draft.marks,
            difficulty=draft.difficulty,
            text=draft.text,
            options=draft.options,
            answer=ans_dict,
            solution_text=draft.solution_text,
            has_figure=False,
            figure_path=None,
            parse_status=ParseStatus.PARSED,
            tag_status=TagStatus.VERIFIED if verif.passed else TagStatus.SUGGESTED,
            text_hash=text_hash,
            verification_metadata=verif.model_dump(),
        )
