"""Backtesting Framework (Module 4).

Executes rolling-origin (walk-forward split) evaluation across past GATE years.
Compares proposed TopicPredictor against:
1. Uniform Baseline (equal topic weights)
2. Naive Frequency Baseline (unweighted historical mark count)

Outputs complete metrics and markdown evaluation report.
"""

from __future__ import annotations

import statistics
from typing import Any, Sequence

from app.analytics.metrics import (
    earth_movers_distance,
    expected_calibration_error,
    kl_divergence,
    must_do_coverage,
    precision_at_k,
    spearman_rank_correlation,
)
from app.analytics.predictor import QuestionRecord, TopicPredictor
from app.analytics.schemas import BacktestFoldResult, BacktestReport, ModelEvaluationMetrics


class BacktestEngine:
    """Rolling-origin evaluator for GATE paper topic priority models."""

    def __init__(
        self,
        predictor: TopicPredictor | None = None,
        eval_window_folds: int = 5,
        history_window_years: int = 10,
    ) -> None:
        self.predictor = predictor or TopicPredictor()
        self.eval_window_folds = eval_window_folds
        self.history_window_years = history_window_years

    def run_backtest(
        self,
        subject_id: str,
        records: Sequence[QuestionRecord | dict[str, Any]],
        taxonomy_topics: list[dict[str, Any]],
        eval_years: list[int] | None = None,
    ) -> BacktestReport:
        """Run rolling-origin walk-forward evaluation.

        Args:
            subject_id: Subject identifier.
            records: List of question records with year, topic_id, marks.
            taxonomy_topics: List of taxonomy topic dicts (id, name, code).
            eval_years: List of test years to evaluate (if None, auto-select last N years).

        Returns:
            BacktestReport containing detailed fold results and aggregated metrics.
        """
        # Standardize question records
        clean_records: list[QuestionRecord] = []
        for r in records:
            if isinstance(r, QuestionRecord):
                clean_records.append(r)
            elif isinstance(r, dict):
                clean_records.append(
                    QuestionRecord(
                        topic_id=str(r["topic_id"]),
                        year=int(r["year"]),
                        marks=float(r["marks"]),
                    )
                )

        if not clean_records:
            raise ValueError("Cannot run backtest on empty question records.")

        all_years = sorted(list({r.year for r in clean_records}))

        if eval_years is None:
            # Auto-select last `eval_window_folds` years (ensuring at least 1 prior training year)
            if len(all_years) < 2:
                raise ValueError("At least 2 distinct years required for backtest.")
            eval_years = all_years[-min(self.eval_window_folds, len(all_years) - 1) :]

        topic_ids = [t["id"] for t in taxonomy_topics]
        folds: list[BacktestFoldResult] = []

        # Map metrics by model across all folds for aggregation
        all_fold_metrics: dict[str, list[ModelEvaluationMetrics]] = {
            "Predictor": [],
            "NaiveFrequency": [],
            "Uniform": [],
        }

        for eval_yr in eval_years:
            # Train split: records with year < eval_yr and >= eval_yr - history_window_years
            train_start = eval_yr - self.history_window_years
            train_records = [
                r for r in clean_records if train_start <= r.year < eval_yr
            ]
            test_records = [r for r in clean_records if r.year == eval_yr]

            train_years = sorted(list({r.year for r in train_records}))
            if not train_years:
                continue

            # Actual test marks by topic
            actual_topic_marks: dict[str, float] = {tid: 0.0 for tid in topic_ids}
            for tr in test_records:
                if tr.topic_id in actual_topic_marks:
                    actual_topic_marks[tr.topic_id] += tr.marks

            total_actual_marks = sum(actual_topic_marks.values())

            # --- Model 1: Proposed TopicPredictor ---
            pred_response = self.predictor.predict(
                subject_id=subject_id,
                subject_name=subject_id,
                records=train_records,
                taxonomy_topics=taxonomy_topics,
                latest_year=eval_yr - 1,
                window_years=self.history_window_years,
            )
            predictor_weights = {i.topic_id: i.priority_score for i in pred_response.all_topics}
            predictor_must_do = {i.topic_id for i in pred_response.must_do_topics}

            metrics_predictor = self._evaluate_model(
                model_name="Predictor",
                predicted_weights=predictor_weights,
                must_do_set=predictor_must_do,
                actual_marks=actual_topic_marks,
                topic_ids=topic_ids,
            )

            # --- Model 2: Naive Raw Frequency Baseline ---
            naive_weights: dict[str, float] = {tid: 0.0 for tid in topic_ids}
            for tr in train_records:
                if tr.topic_id in naive_weights:
                    naive_weights[tr.topic_id] += tr.marks
            # Must-do for naive: top 60% topics by unweighted marks
            sorted_naive = sorted(topic_ids, key=lambda tid: naive_weights[tid], reverse=True)
            n_must = max(1, round(len(topic_ids) * 0.6))
            naive_must_do = set(sorted_naive[:n_must])

            metrics_naive = self._evaluate_model(
                model_name="NaiveFrequency",
                predicted_weights=naive_weights,
                must_do_set=naive_must_do,
                actual_marks=actual_topic_marks,
                topic_ids=topic_ids,
            )

            # --- Model 3: Uniform Baseline ---
            uniform_val = 1.0 / len(topic_ids) if topic_ids else 1.0
            uniform_weights: dict[str, float] = {tid: uniform_val for tid in topic_ids}
            uniform_must_do = set(topic_ids[:n_must])

            metrics_uniform = self._evaluate_model(
                model_name="Uniform",
                predicted_weights=uniform_weights,
                must_do_set=uniform_must_do,
                actual_marks=actual_topic_marks,
                topic_ids=topic_ids,
            )

            # Collect metrics
            metrics_by_model = {
                "Predictor": metrics_predictor,
                "NaiveFrequency": metrics_naive,
                "Uniform": metrics_uniform,
            }

            for m_name, m_val in metrics_by_model.items():
                all_fold_metrics[m_name].append(m_val)

            fold_result = BacktestFoldResult(
                eval_year=eval_yr,
                train_years=train_years,
                total_actual_marks=total_actual_marks,
                actual_topic_marks=actual_topic_marks,
                metrics_by_model=metrics_by_model,
            )
            folds.append(fold_result)

        # Aggregate summary statistics across all folds
        summary_by_model: dict[str, dict[str, float]] = {}
        for m_name, m_list in all_fold_metrics.items():
            if not m_list:
                continue
            summary_by_model[m_name] = self._aggregate_model_stats(m_list)

        return BacktestReport(
            subject_id=subject_id,
            eval_years=eval_years,
            folds=folds,
            summary_by_model=summary_by_model,
        )

    def _evaluate_model(
        self,
        model_name: str,
        predicted_weights: dict[str, float],
        must_do_set: set[str],
        actual_marks: dict[str, float],
        topic_ids: list[str],
    ) -> ModelEvaluationMetrics:
        """Evaluate a model's prediction against actual paper topic marks."""
        # Align vectors for correlation
        pred_vec = [predicted_weights.get(tid, 0.0) for tid in topic_ids]
        act_vec = [actual_marks.get(tid, 0.0) for tid in topic_ids]

        cov = must_do_coverage(must_do_set, actual_marks)
        rho = spearman_rank_correlation(pred_vec, act_vec)
        p3 = precision_at_k(predicted_weights, actual_marks, k=3)
        p5 = precision_at_k(predicted_weights, actual_marks, k=5)
        kl = kl_divergence(predicted_weights, actual_marks)
        ece_val = expected_calibration_error(predicted_weights, actual_marks)
        emd_val = earth_movers_distance(predicted_weights, actual_marks)

        return ModelEvaluationMetrics(
            model_name=model_name,
            must_do_coverage=round(cov, 4),
            spearman_correlation=round(rho, 4),
            precision_at_3=round(p3, 4),
            precision_at_5=round(p5, 4),
            kl_divergence=round(kl, 4),
            ece=round(ece_val, 4),
            earth_movers_distance=round(emd_val, 4),
        )

    def _aggregate_model_stats(
        self, metrics_list: list[ModelEvaluationMetrics]
    ) -> dict[str, float]:
        """Compute mean and std for each metric across folds."""
        metric_names = [
            "must_do_coverage",
            "spearman_correlation",
            "precision_at_3",
            "precision_at_5",
            "kl_divergence",
            "ece",
            "earth_movers_distance",
        ]
        result: dict[str, float] = {}

        for m_name in metric_names:
            vals = [getattr(m, m_name) for m in metrics_list]
            mean_val = statistics.mean(vals) if vals else 0.0
            std_val = statistics.stdev(vals) if len(vals) > 1 else 0.0
            result[f"{m_name}_mean"] = round(mean_val, 4)
            result[f"{m_name}_std"] = round(std_val, 4)

        return result
