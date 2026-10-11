"""Pydantic schemas for prediction engine and backtesting results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.subject import PriorityBucket

TREND_DISCLAIMER: str = (
    "All outputs are trend-based guidance. GATE question selection is non-deterministic."
)


class TopicPriorityItem(BaseModel):
    """Priority calculation details for a single topic."""

    topic_id: str
    topic_name: str
    topic_code: str
    weighted_marks: float = Field(ge=0.0, description="Recency-weighted mark sum")
    consistency: float = Field(ge=0.0, le=1.0, description="Fraction of years appeared")
    trend: float = Field(description="Linear slope of marks over years")
    gap: float = Field(ge=0.0, description="Normalized gap score (capped at 1.5)")
    priority_score: float = Field(ge=0.0, le=1.0, description="Composite priority score [0, 1]")
    bucket: PriorityBucket
    rationale: str
    confidence: str = Field(description="high | medium | low")
    total_historical_appearances: int = Field(ge=0)
    avg_marks_per_year: float = Field(ge=0.0)
    last_appeared_year: int | None = None

    model_config = {"from_attributes": True}


class SubjectPriorityResponse(BaseModel):
    """API response model for subject topic priority endpoint."""

    subject_id: str
    subject_name: str
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = TREND_DISCLAIMER
    must_do_topics: list[TopicPriorityItem] = Field(default_factory=list)
    should_do_topics: list[TopicPriorityItem] = Field(default_factory=list)
    skip_if_short_topics: list[TopicPriorityItem] = Field(default_factory=list)
    all_topics: list[TopicPriorityItem] = Field(default_factory=list)


class ModelEvaluationMetrics(BaseModel):
    """Evaluation metrics for a single model on a single evaluation fold."""

    model_name: str
    must_do_coverage: float = Field(
        ge=0.0, le=1.0, description="Fraction of actual test marks covered by Must-Do topics"
    )
    spearman_correlation: float = Field(
        ge=-1.0, le=1.0, description="Spearman rank correlation with actual topic marks"
    )
    precision_at_3: float = Field(ge=0.0, le=1.0, description="Top-3 topic precision")
    precision_at_5: float = Field(ge=0.0, le=1.0, description="Top-5 topic precision")
    kl_divergence: float = Field(ge=0.0, description="KL divergence vs actual topic distribution")
    ece: float = Field(ge=0.0, le=1.0, description="Expected Calibration Error")
    earth_movers_distance: float = Field(ge=0.0, description="Wasserstein / EMD score")


class BacktestFoldResult(BaseModel):
    """Results for a single walk-forward evaluation year."""

    eval_year: int
    train_years: list[int]
    total_actual_marks: float
    actual_topic_marks: dict[str, float]
    metrics_by_model: dict[str, ModelEvaluationMetrics]


class BacktestReport(BaseModel):
    """Complete rolling-origin backtest evaluation report across all test folds."""

    subject_id: str
    eval_years: list[int]
    folds: list[BacktestFoldResult]
    summary_by_model: dict[str, dict[str, float]] = Field(
        description="Aggregated mean and std metrics per model"
    )
    disclaimer: str = TREND_DISCLAIMER
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        """Render backtest results as a formatted markdown document."""
        lines = [
            "# GATE Topic Predictor - Backtest Evaluation Report",
            f"**Subject ID**: {self.subject_id}",
            f"**Evaluation Window**: {min(self.eval_years)} - {max(self.eval_years)}",
            f"**Generated**: {self.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            f"> **Disclaimer**: {self.disclaimer}",
            "",
            "## Summary Metrics Across All Folds (Mean +/- Std)",
            "",
            "| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div | ECE | EMD |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]

        for model_name, stats in self.summary_by_model.items():
            lines.append(
                f"| **{model_name}** "
                f"| {stats.get('must_do_coverage_mean', 0.0):.1%} +/- {stats.get('must_do_coverage_std', 0.0):.1%} "
                f"| {stats.get('spearman_correlation_mean', 0.0):.3f} +/- {stats.get('spearman_correlation_std', 0.0):.3f} "
                f"| {stats.get('precision_at_3_mean', 0.0):.1%} +/- {stats.get('precision_at_3_std', 0.0):.1%} "
                f"| {stats.get('precision_at_5_mean', 0.0):.1%} +/- {stats.get('precision_at_5_std', 0.0):.1%} "
                f"| {stats.get('kl_divergence_mean', 0.0):.4f} "
                f"| {stats.get('ece_mean', 0.0):.4f} "
                f"| {stats.get('earth_movers_distance_mean', 0.0):.4f} |"
            )

        lines.extend(["", "## Detailed Folds", ""])

        for fold in self.folds:
            lines.extend([
                f"### Fold Year: {fold.eval_year}",
                f"- **Train Years**: {fold.train_years[0]} - {fold.train_years[-1]}",
                f"- **Total Test Marks**: {fold.total_actual_marks:.1f}",
                "",
                "| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |",
                "| --- | --- | --- | --- | --- | --- |",
            ])
            for model_name, m in fold.metrics_by_model.items():
                lines.append(
                    f"| {model_name} | {m.must_do_coverage:.1%} | {m.spearman_correlation:.3f} | "
                    f"{m.precision_at_3:.1%} | {m.precision_at_5:.1%} | {m.kl_divergence:.4f} |"
                )
            lines.append("")

        return "\n".join(lines)
