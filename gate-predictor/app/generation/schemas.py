"""Pydantic schemas for question generation and verification gate (Module 5)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.db.models.question import DifficultyLevel, QuestionType


class GeneratedQuestionDraft(BaseModel):
    """Raw JSON structure expected from LLM question generation."""

    text: str = Field(min_length=10, description="Problem statement with LaTeX math formatting")
    options: dict[str, str] | None = Field(
        default=None, description="Dict of options e.g. {'A': '...', 'B': '...', 'C': '...', 'D': '...'}"
    )
    qtype: QuestionType = Field(description="MCQ | MSQ | NAT")
    marks: int = Field(ge=1, le=2, description="Marks (1 or 2)")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)
    answer: Any = Field(
        description="MCQ: ['A'], MSQ: ['A', 'C'], NAT: {'value': 4.5, 'min': 4.0, 'max': 5.0}"
    )
    solution_text: str = Field(default="", description="Step-by-step solution")
    topic_id: str = Field(description="Taxonomy topic ID")
    subtopic_id: str | None = Field(default=None, description="Taxonomy subtopic ID")

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: dict[str, str] | None, info: Any) -> dict[str, str] | None:
        """Options must be None for NAT, and contain at least A, B, C, D for MCQ/MSQ."""
        qtype = info.data.get("qtype")
        if qtype == QuestionType.NAT:
            return None
        if qtype in (QuestionType.MCQ, QuestionType.MSQ):
            if not v or len(v) < 4:
                raise ValueError(f"MCQ/MSQ questions require at least 4 options, got {v}")
        return v


class VerificationResult(BaseModel):
    """Detailed audit outcome of the 5-step verification gate."""

    passed: bool = Field(description="True if all 5 verification steps passed")
    step_results: dict[str, bool] = Field(
        default_factory=dict,
        description="Dict mapping step_name -> pass/fail boolean",
    )
    solver_answer: Any = Field(default=None, description="Answer derived by independent solver LLM")
    generated_answer: Any = Field(default=None, description="Original answer key from draft")
    similarity_score: float = Field(default=0.0, description="Max cosine similarity to existing bank")
    failure_reasons: list[str] = Field(default_factory=list, description="List of failure messages")


class SolveAttemptResponse(BaseModel):
    """Output structure from Step 1 independent LLM solver."""

    solved_answer: Any = Field(description="Solved answer: list of option keys or numeric value")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="")
