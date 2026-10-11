"""Subject classifier for GATE CS questions.

Classifies each ingested question into one of:
- Target subject (e.g. operating_systems)
- Other GATE CS subjects (data_structures, algorithms, etc.)
- engineering_mathematics
- general_aptitude
"""

from __future__ import annotations

from app.core.llm_client import LLMClient, SubjectClassification
from app.core.logging import get_logger

logger = get_logger(__name__)

# All recognised GATE CS subject areas
GATE_CS_SUBJECTS: list[str] = [
    "operating_systems",
    "data_structures",
    "algorithms",
    "databases",
    "computer_networks",
    "compiler_design",
    "theory_of_computation",
    "digital_logic",
    "computer_organization",
    "programming_languages",
    "software_engineering",
    "engineering_mathematics",
    "general_aptitude",
]


class SubjectClassifier:
    """Classifies questions into GATE CS subject areas using an LLM.

    Args:
        llm_client: An LLMClient instance for classification.
        target_subject: The primary subject of interest.
    """

    def __init__(self, llm_client: LLMClient, target_subject: str = "operating_systems") -> None:
        self._llm_client = llm_client
        self._target_subject = target_subject

    def classify(
        self,
        question_text: str,
        options: dict[str, str] | None = None,
    ) -> SubjectClassification:
        """Classify a single question into a GATE CS subject.

        Args:
            question_text: The full question text.
            options: Option dict if MCQ/MSQ, None for NAT.

        Returns:
            A SubjectClassification result.
        """
        result = self._llm_client.classify_subject(
            question_text=question_text,
            options=options,
            available_subjects=GATE_CS_SUBJECTS,
        )

        logger.debug(
            "question_classified",
            classified_subject=result.classified_subject,
            confidence=result.confidence,
            is_target=(result.classified_subject == self._target_subject),
        )

        return result

    def is_target_subject(self, classification: SubjectClassification) -> bool:
        """Check if a classification result matches the target subject.

        Args:
            classification: The classification result.

        Returns:
            True if the classified subject matches the target.
        """
        return classification.classified_subject == self._target_subject
