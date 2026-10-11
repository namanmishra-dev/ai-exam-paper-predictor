"""Custom exception hierarchy for the application.

All exceptions inherit from GatePredictorError so callers can catch broadly
or narrowly as needed.
"""

from __future__ import annotations


class GatePredictorError(Exception):
    """Base exception for the entire application."""


# ── Ingestion ────────────────────────────────────────────────────────────────

class IngestionError(GatePredictorError):
    """Raised when the ingestion pipeline encounters a fatal error."""


class ParseError(IngestionError):
    """Raised when a PDF page cannot be parsed into structured questions."""


class AnswerKeyError(IngestionError):
    """Raised when the answer key cannot be matched to questions."""


class PaperAssertionError(IngestionError):
    """Raised when a paper does not meet the expected 65-question / 100-mark assertion."""

    def __init__(self, year: int, set_no: int, actual_questions: int, actual_marks: int) -> None:
        self.year = year
        self.set_no = set_no
        self.actual_questions = actual_questions
        self.actual_marks = actual_marks
        super().__init__(
            f"Paper {year} Set {set_no}: expected 65 questions / 100 marks, "
            f"got {actual_questions} questions / {actual_marks} marks"
        )


# ── Tagging ──────────────────────────────────────────────────────────────────

class TaggingError(GatePredictorError):
    """Raised when the tagging pipeline encounters a fatal error."""


class TaxonomyError(GatePredictorError):
    """Raised when the taxonomy YAML is invalid or inconsistent."""


# ── Generation ───────────────────────────────────────────────────────────────

class GenerationError(GatePredictorError):
    """Raised when question generation fails after retries."""


class VerificationError(GatePredictorError):
    """Raised when a generated question fails the verification gate."""


# ── Assembler ────────────────────────────────────────────────────────────────

class AssemblerError(GatePredictorError):
    """Raised when the mock paper assembler cannot satisfy constraints."""


# ── Duplicate ────────────────────────────────────────────────────────────────

class DuplicateQuestionError(IngestionError):
    """Raised when a question is a near-duplicate of an existing record."""

    def __init__(self, question_text_preview: str, similarity: float) -> None:
        self.similarity = similarity
        super().__init__(
            f"Duplicate detected (similarity={similarity:.3f}): {question_text_preview[:80]}..."
        )


# ── LLM ──────────────────────────────────────────────────────────────────────

class LLMClientError(GatePredictorError):
    """Raised when an LLM API call fails."""


class LLMRateLimitError(LLMClientError):
    """Raised when the LLM API rate limit is hit."""
