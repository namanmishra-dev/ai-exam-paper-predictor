"""Pydantic schemas for mock paper assembler and blueprint constraints (Module 6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models.question import DifficultyLevel, QuestionType


class PaperBlueprint(BaseModel):
    """Configuration blueprint for assembling a mock paper."""

    total_marks: float = Field(default=100.0, ge=10.0, description="Target total marks (100 for full paper, 25 for mini)")
    total_questions: int = Field(default=65, ge=5, description="Target question count (65 for full GATE paper)")
    duration_minutes: int = Field(default=180, ge=15, description="Duration in minutes (180 for full paper)")
    pyq_ratio: float = Field(default=0.70, ge=0.0, le=1.0, description="Target ratio of official PYQs vs generated")
    
    # Difficulty mix (must sum to 1.0)
    difficulty_mix: dict[DifficultyLevel, float] = Field(
        default_factory=lambda: {
            DifficultyLevel.EASY: 0.30,
            DifficultyLevel.MEDIUM: 0.50,
            DifficultyLevel.HARD: 0.20,
        }
    )
    
    # Question type mix
    qtype_mix: dict[QuestionType, float] = Field(
        default_factory=lambda: {
            QuestionType.MCQ: 0.50,
            QuestionType.MSQ: 0.25,
            QuestionType.NAT: 0.25,
        }
    )

    focus_topic_ids: list[str] = Field(default_factory=list, description="Optional topic IDs to prioritize")
    seed: int = Field(default=42, description="Random seed for reproducible paper generation")


class AssemblyConstraintValidation(BaseModel):
    """Validation audit report checking if assembled paper meets blueprint constraints."""

    is_valid: bool = Field(description="True if all hard constraints are satisfied")
    target_marks: float
    actual_marks: float
    target_questions: int
    actual_questions: int
    actual_mcq_count: int
    actual_msq_count: int
    actual_nat_count: int
    actual_pyq_count: int
    actual_generated_count: int
    topic_mark_distribution: dict[str, float] = Field(default_factory=dict)
    validation_messages: list[str] = Field(default_factory=list)
