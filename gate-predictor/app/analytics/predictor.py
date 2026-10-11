"""Topic Priority Prediction Engine (Module 3).

Statistical, explainable predictor for GATE CS subject topics based on:
1. Recency-weighted mark distribution: w(y) = exp(-lambda * (Y - y))
2. Consistency score: fraction of historical years in which topic appeared
3. Trend score: linear regression slope of topic marks over years
4. Gap score: ratio of years since last appearance to average historical gap (capped at 1.5)

Precomputes offline and returns PriorityBucket assignments, rationales, and confidence labels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from app.analytics.schemas import SubjectPriorityResponse, TopicPriorityItem, TREND_DISCLAIMER
from app.core.config import settings
from app.db.models.subject import PriorityBucket


@dataclass
class QuestionRecord:
    """Lightweight representation of a question for priority calculation."""

    topic_id: str
    year: int
    marks: float


class TopicPredictor:
    """Pure, deterministic predictor engine computing topic priorities."""

    def __init__(
        self,
        lambda_decay: float | None = None,
        weight_weighted_marks: float | None = None,
        weight_trend: float | None = None,
        weight_gap: float | None = None,
        weight_consistency: float | None = None,
        must_do_pct: int | None = None,
        should_do_pct: int | None = None,
    ) -> None:
        self.lambda_decay = lambda_decay if lambda_decay is not None else settings.prediction.lambda_decay
        self.w_wm = (
            weight_weighted_marks
            if weight_weighted_marks is not None
            else settings.prediction.priority_weight_weighted_marks
        )
        self.w_trend = (
            weight_trend if weight_trend is not None else settings.prediction.priority_weight_trend
        )
        self.w_gap = (
            weight_gap if weight_gap is not None else settings.prediction.priority_weight_gap
        )
        self.w_consistency = (
            weight_consistency
            if weight_consistency is not None
            else settings.prediction.priority_weight_consistency
        )
        self.must_do_pct = (
            must_do_pct if must_do_pct is not None else settings.prediction.bucket_must_do_percent
        )
        self.should_do_pct = (
            should_do_pct
            if should_do_pct is not None
            else settings.prediction.bucket_should_do_percent
        )

    def predict(
        self,
        subject_id: str,
        subject_name: str,
        records: Sequence[QuestionRecord | dict[str, Any]],
        taxonomy_topics: list[dict[str, Any]],
        latest_year: int | None = None,
        window_years: int = 10,
    ) -> SubjectPriorityResponse:
        """Calculate topic priority ranking, scores, buckets, and rationales.

        Args:
            subject_id: Subject ID (e.g. "operating_systems").
            subject_name: Subject display name.
            records: List of question records (or dicts with topic_id, year, marks).
            taxonomy_topics: List of topic metadata dicts (id, name, code).
            latest_year: Target evaluation year (defaults to max year in records).
            window_years: Historical year window size (default 10 years).

        Returns:
            SubjectPriorityResponse containing categorized topic priority items.
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
            # Empty record case: return uniform baseline with low confidence
            return self._build_empty_response(subject_id, subject_name, taxonomy_topics)

        # Determine year window
        all_years = [r.year for r in clean_records]
        end_year = latest_year if latest_year is not None else max(all_years)
        start_year = end_year - window_years + 1
        year_list = list(range(start_year, end_year + 1))
        n_years = len(year_list)

        # Map taxonomy topics
        topic_map: dict[str, dict[str, Any]] = {
            t["id"]: {"name": t["name"], "code": t.get("code", t["id"])} for t in taxonomy_topics
        }

        # Aggregate marks per topic per year
        topic_year_marks: dict[str, dict[int, float]] = {tid: {y: 0.0 for y in year_list} for tid in topic_map}
        topic_question_counts: dict[str, int] = {tid: 0 for tid in topic_map}

        for r in clean_records:
            if r.topic_id in topic_year_marks and r.year in topic_year_marks[r.topic_id]:
                topic_year_marks[r.topic_id][r.year] += r.marks
                topic_question_counts[r.topic_id] += 1

        # Compute raw metrics per topic
        raw_metrics: dict[str, dict[str, float | int | list[int] | None]] = {}

        for tid in topic_map:
            y_marks = topic_year_marks[tid]
            q_count = topic_question_counts[tid]

            # 1. Recency Weighted Marks: w(y) = exp(-lambda * (Y - y))
            weighted_marks = sum(
                math.exp(-self.lambda_decay * (end_year - y)) * m for y, m in y_marks.items()
            )

            # 2. Consistency: fraction of years with marks > 0
            appeared_years = sorted([y for y, m in y_marks.items() if m > 0])
            consistency = len(appeared_years) / n_years if n_years > 0 else 0.0

            # 3. Trend: Linear regression slope of marks over years
            trend = self._calculate_linear_slope(year_list, [y_marks[y] for y in year_list])

            # 4. Gap score: years since last appearance / mean gap (capped at 1.5)
            gap_score, last_year = self._calculate_gap_score(appeared_years, end_year, n_years)

            # Averages and historical metrics
            total_historical_appearances = len(appeared_years)
            total_marks = sum(y_marks.values())
            avg_marks_per_year = total_marks / n_years if n_years > 0 else 0.0

            raw_metrics[tid] = {
                "weighted_marks": weighted_marks,
                "consistency": consistency,
                "trend": trend,
                "gap": gap_score,
                "total_historical_appearances": total_historical_appearances,
                "avg_marks_per_year": avg_marks_per_year,
                "last_appeared_year": last_year,
                "question_count": q_count,
            }

        # Normalize components across all topics to [0, 1]
        normalized_metrics = self._normalize_metrics(raw_metrics)

        # Compute composite priority scores
        topic_scores: dict[str, float] = {}
        for tid in topic_map:
            norm = normalized_metrics[tid]
            score = (
                self.w_wm * norm["weighted_marks"]
                + self.w_trend * norm["trend"]
                + self.w_gap * norm["gap"]
                + self.w_consistency * norm["consistency"]
            )
            topic_scores[tid] = round(max(0.0, min(1.0, score)), 4)

        # Sort topics descending by weighted_marks for bucket assignment
        sorted_topic_ids = sorted(
            topic_map.keys(),
            key=lambda tid: (
                raw_metrics[tid]["weighted_marks"],
                topic_scores[tid],
            ),
            reverse=True,
        )

        # Assign priority buckets (Must-Do, Should-Do, Skip-if-short)
        bucket_assignments = self._assign_buckets(sorted_topic_ids, raw_metrics)

        # Build TopicPriorityItem results
        items: list[TopicPriorityItem] = []
        for tid in sorted_topic_ids:
            raw = raw_metrics[tid]
            meta = topic_map[tid]
            bucket = bucket_assignments[tid]
            score = topic_scores[tid]

            # Generate rationale string
            rationale = self._generate_rationale(
                topic_name=meta["name"],
                appearances=int(raw["total_historical_appearances"]),
                n_years=n_years,
                consistency=float(raw["consistency"]),
                avg_marks=float(raw["avg_marks_per_year"]),
                last_year=raw["last_appeared_year"],  # type: ignore[arg-type]
                end_year=end_year,
                score=score,
            )

            # Determine confidence label
            confidence = self._determine_confidence(
                appearances=int(raw["total_historical_appearances"]),
                question_count=int(raw["question_count"]),
            )

            item = TopicPriorityItem(
                topic_id=tid,
                topic_name=meta["name"],
                topic_code=meta["code"],
                weighted_marks=round(float(raw["weighted_marks"]), 4),
                consistency=round(float(raw["consistency"]), 4),
                trend=round(float(raw["trend"]), 4),
                gap=round(float(raw["gap"]), 4),
                priority_score=score,
                bucket=bucket,
                rationale=rationale,
                confidence=confidence,
                total_historical_appearances=int(raw["total_historical_appearances"]),
                avg_marks_per_year=round(float(raw["avg_marks_per_year"]), 2),
                last_appeared_year=raw["last_appeared_year"],  # type: ignore[arg-type]
            )
            items.append(item)

        # Separate items into buckets
        must_do = [i for i in items if i.bucket == PriorityBucket.MUST_DO]
        should_do = [i for i in items if i.bucket == PriorityBucket.SHOULD_DO]
        skip_if_short = [i for i in items if i.bucket == PriorityBucket.SKIP_IF_SHORT]

        return SubjectPriorityResponse(
            subject_id=subject_id,
            subject_name=subject_name,
            disclaimer=TREND_DISCLAIMER,
            must_do_topics=must_do,
            should_do_topics=should_do,
            skip_if_short_topics=skip_if_short,
            all_topics=items,
        )

    def _calculate_linear_slope(self, years: list[int], marks: list[float]) -> float:
        """Calculate linear regression slope of marks over years."""
        n = len(years)
        if n < 2:
            return 0.0
        mean_y = sum(years) / n
        mean_m = sum(marks) / n
        num = sum((years[i] - mean_y) * (marks[i] - mean_m) for i in range(n))
        den = sum((years[i] - mean_y) ** 2 for i in range(n))
        if den == 0.0:
            return 0.0
        return num / den

    def _calculate_gap_score(
        self, appeared_years: list[int], end_year: int, window_years: int
    ) -> tuple[float, int | None]:
        """Calculate gap metric (ratio of years since last appearance to average gap)."""
        if not appeared_years:
            return 1.0, None

        last_year = max(appeared_years)
        years_since_last = end_year - last_year

        if len(appeared_years) < 2:
            gap_ratio = years_since_last / window_years
        else:
            gaps = [
                appeared_years[i + 1] - appeared_years[i]
                for i in range(len(appeared_years) - 1)
            ]
            mean_gap = sum(gaps) / len(gaps) if gaps else 1.0
            gap_ratio = years_since_last / mean_gap if mean_gap > 0 else 1.0

        gap_score = min(1.5, gap_ratio)
        return gap_score, last_year

    def _normalize_metrics(
        self, raw_metrics: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        """Min-max normalize weighted_marks, trend, gap, and consistency across topics to [0, 1]."""
        normalized: dict[str, dict[str, float]] = {tid: {} for tid in raw_metrics}

        for metric in ["weighted_marks", "trend", "gap", "consistency"]:
            vals = [float(raw_metrics[tid][metric]) for tid in raw_metrics]
            min_v = min(vals) if vals else 0.0
            max_v = max(vals) if vals else 1.0

            for tid in raw_metrics:
                val = float(raw_metrics[tid][metric])
                if max_v > min_v:
                    norm = (val - min_v) / (max_v - min_v)
                else:
                    norm = 0.5 if val > 0 else 0.0
                normalized[tid][metric] = norm

        return normalized

    def _assign_buckets(
        self,
        sorted_topic_ids: list[str],
        raw_metrics: dict[str, dict[str, Any]],
    ) -> dict[str, PriorityBucket]:
        """Assign topics to Must-Do (~60%), Should-Do (~25%), and Skip-If-Short (~15%)."""
        total_wm = sum(float(raw_metrics[tid]["weighted_marks"]) for tid in sorted_topic_ids)
        assignments: dict[str, PriorityBucket] = {}

        if total_wm <= 0:
            # Fallback uniform division if no marks present
            n = len(sorted_topic_ids)
            n_must = max(1, math.ceil(n * 0.6))
            n_should = max(0, math.ceil(n * 0.25))

            for i, tid in enumerate(sorted_topic_ids):
                if i < n_must:
                    assignments[tid] = PriorityBucket.MUST_DO
                elif i < n_must + n_should:
                    assignments[tid] = PriorityBucket.SHOULD_DO
                else:
                    assignments[tid] = PriorityBucket.SKIP_IF_SHORT
            return assignments

        cum_weight = 0.0
        must_threshold = total_wm * (self.must_do_pct / 100.0)
        should_threshold = total_wm * ((self.must_do_pct + self.should_do_pct) / 100.0)

        for i, tid in enumerate(sorted_topic_ids):
            wm = float(raw_metrics[tid]["weighted_marks"])
            cum_weight += wm

            # Ensure at least first topic goes to Must-Do
            if i == 0 or cum_weight <= must_threshold:
                assignments[tid] = PriorityBucket.MUST_DO
            elif cum_weight <= should_threshold:
                assignments[tid] = PriorityBucket.SHOULD_DO
            else:
                assignments[tid] = PriorityBucket.SKIP_IF_SHORT

        return assignments

    def _generate_rationale(
        self,
        topic_name: str,
        appearances: int,
        n_years: int,
        consistency: float,
        avg_marks: float,
        last_year: int | None,
        end_year: int,
        score: float,
    ) -> str:
        """Build human-readable explanatory rationale for topic score."""
        if last_year is not None:
            gap = end_year - last_year
            recency_str = (
                f"last seen in {last_year} ({gap}-year gap)"
                if gap > 0
                else f"featured in recent {last_year} paper"
            )
        else:
            recency_str = "never featured in evaluated window"

        return (
            f"Appeared in {appearances} of {n_years} years ({consistency:.0%} consistency). "
            f"Average {avg_marks:.1f} marks per year; {recency_str}. "
            f"Composite Priority Score: {score:.2f}."
        )

    def _determine_confidence(self, appearances: int, question_count: int) -> str:
        """Label prediction confidence based on data sparsity."""
        if appearances >= 6 or question_count >= 10:
            return "high"
        if appearances >= 3 or question_count >= 4:
            return "medium"
        return "low"

    def _build_empty_response(
        self,
        subject_id: str,
        subject_name: str,
        taxonomy_topics: list[dict[str, Any]],
    ) -> SubjectPriorityResponse:
        """Handle zero data case cleanly."""
        items: list[TopicPriorityItem] = []
        for t in taxonomy_topics:
            items.append(
                TopicPriorityItem(
                    topic_id=t["id"],
                    topic_name=t["name"],
                    topic_code=t.get("code", t["id"]),
                    weighted_marks=0.0,
                    consistency=0.0,
                    trend=0.0,
                    gap=0.0,
                    priority_score=0.5,
                    bucket=PriorityBucket.MUST_DO,
                    rationale=f"Insufficient data for {t['name']}. Default score assigned.",
                    confidence="low",
                    total_historical_appearances=0,
                    avg_marks_per_year=0.0,
                    last_appeared_year=None,
                )
            )
        return SubjectPriorityResponse(
            subject_id=subject_id,
            subject_name=subject_name,
            disclaimer=TREND_DISCLAIMER,
            must_do_topics=items,
            should_do_topics=[],
            skip_if_short_topics=[],
            all_topics=items,
        )
