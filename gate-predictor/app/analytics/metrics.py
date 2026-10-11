"""Evaluation and comparison metrics for backtesting prediction models (Module 4).

Provides:
- Spearman Rank Correlation Coefficient
- Precision @ K (e.g. K=3, K=5)
- Must-Do Topic Mark Coverage Fraction
- Kullback-Leibler (KL) Divergence
- Expected Calibration Error (ECE)
- Earth Mover's Distance (EMD / Wasserstein-1)
"""

from __future__ import annotations

import math
from typing import Sequence


def spearman_rank_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    """Compute Spearman's rank correlation coefficient between two numeric vectors.

    Args:
        x: Vector of predicted scores or weights.
        y: Vector of actual marks or ground truth weights.

    Returns:
        Spearman correlation rho in range [-1.0, 1.0].
    """
    n = len(x)
    if n < 2 or len(y) != n:
        return 0.0

    rx = _rank_vector(x)
    ry = _rank_vector(y)

    d_sq_sum = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    num = 6.0 * d_sq_sum
    den = float(n * (n * n - 1))

    if den == 0.0:
        return 0.0

    return max(-1.0, min(1.0, 1.0 - (num / den)))


def _rank_vector(values: Sequence[float]) -> list[float]:
    """Convert values to rank values, taking average for ties."""
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i
        while j < n - 1 and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        # Average rank for tied group
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1

    return ranks


def precision_at_k(predicted_scores: dict[str, float], actual_marks: dict[str, float], k: int = 3) -> float:
    """Compute Precision@K overlap between top-K predicted topics and top-K actual topics.

    Args:
        predicted_scores: Dict mapping topic_id -> predicted priority score/weight.
        actual_marks: Dict mapping topic_id -> actual marks obtained in evaluation paper.
        k: Top-K threshold.

    Returns:
        Fraction of top-K predicted topics present in top-K actual topics [0.0, 1.0].
    """
    if not predicted_scores or not actual_marks or k <= 0:
        return 0.0

    # Sort topics by predicted score descending
    top_k_pred = set(
        sorted(predicted_scores.keys(), key=lambda tid: predicted_scores[tid], reverse=True)[:k]
    )

    # Sort topics by actual marks descending
    top_k_actual = set(
        sorted(actual_marks.keys(), key=lambda tid: actual_marks[tid], reverse=True)[:k]
    )

    if not top_k_pred or not top_k_actual:
        return 0.0

    overlap = top_k_pred.intersection(top_k_actual)
    return len(overlap) / min(k, len(top_k_pred))


def must_do_coverage(
    must_do_topic_ids: set[str] | list[str], actual_marks: dict[str, float]
) -> float:
    """Compute the fraction of actual test paper marks covered by predicted Must-Do topics.

    Args:
        must_do_topic_ids: Topics assigned to the Must-Do bucket.
        actual_marks: Dict mapping topic_id -> actual marks in evaluation paper.

    Returns:
        Coverage fraction in range [0.0, 1.0].
    """
    total_actual_marks = sum(actual_marks.values())
    if total_actual_marks <= 0.0:
        return 1.0

    must_do_set = set(must_do_topic_ids)
    covered_marks = sum(marks for tid, marks in actual_marks.items() if tid in must_do_set)

    return max(0.0, min(1.0, covered_marks / total_actual_marks))


def kl_divergence(
    p_pred: Sequence[float] | dict[str, float],
    p_actual: Sequence[float] | dict[str, float],
    epsilon: float = 1e-7,
) -> float:
    """Compute Kullback-Leibler Divergence D_KL(P_pred || P_actual).

    Smooths distributions using epsilon to avoid division by zero or log(0).
    """
    if isinstance(p_pred, dict) and isinstance(p_actual, dict):
        all_keys = sorted(set(p_pred.keys()).union(set(p_actual.keys())))
        vec_pred = [p_pred.get(k, 0.0) for k in all_keys]
        vec_actual = [p_actual.get(k, 0.0) for k in all_keys]
    else:
        vec_pred = list(p_pred)  # type: ignore[arg-type]
        vec_actual = list(p_actual)  # type: ignore[arg-type]

    n = len(vec_pred)
    if n == 0 or len(vec_actual) != n:
        return 0.0

    # Normalize to probability distributions
    sum_pred = sum(vec_pred) + n * epsilon
    sum_act = sum(vec_actual) + n * epsilon

    norm_pred = [(v + epsilon) / sum_pred for v in vec_pred]
    norm_act = [(v + epsilon) / sum_act for v in vec_actual]

    kl = sum(p * math.log(p / q) for p, q in zip(norm_pred, norm_act))
    return max(0.0, float(kl))


def expected_calibration_error(
    predicted_weights: dict[str, float],
    actual_marks: dict[str, float],
    n_bins: int = 5,
) -> float:
    """Compute Expected Calibration Error (ECE) between predicted probabilities and actual mark shares."""
    if not predicted_weights:
        return 0.0

    topics = sorted(predicted_weights.keys())
    n = len(topics)
    if n == 0:
        return 0.0

    sum_pred = sum(predicted_weights.values()) or 1.0
    sum_act = sum(actual_marks.values()) or 1.0

    preds = [predicted_weights[t] / sum_pred for t in topics]
    acts = [actual_marks.get(t, 0.0) / sum_act for t in topics]

    # Partition into n_bins
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    bin_size = 1.0 / n_bins

    for p, a in zip(preds, acts):
        b_idx = min(n_bins - 1, int(p / bin_size))
        bins[b_idx].append((p, a))

    ece = 0.0
    for b in bins:
        if not b:
            continue
        bin_count = len(b)
        avg_pred = sum(p for p, _ in b) / bin_count
        avg_act = sum(a for _, a in b) / bin_count
        ece += (bin_count / n) * abs(avg_pred - avg_act)

    return round(float(ece), 6)


def earth_movers_distance(
    p_pred: dict[str, float],
    p_actual: dict[str, float],
) -> float:
    """Compute 1D Earth Mover's Distance (Wasserstein-1 metric) between normalized topic distributions."""
    if not p_pred and not p_actual:
        return 0.0

    all_keys = sorted(set(p_pred.keys()).union(set(p_actual.keys())))
    if not all_keys:
        return 0.0

    sum_p = sum(p_pred.values()) or 1.0
    sum_a = sum(p_actual.values()) or 1.0

    vec_p = [p_pred.get(k, 0.0) / sum_p for k in all_keys]
    vec_a = [p_actual.get(k, 0.0) / sum_a for k in all_keys]

    cum_p = 0.0
    cum_a = 0.0
    emd = 0.0

    for vp, va in zip(vec_p, vec_a):
        cum_p += vp
        cum_a += va
        emd += abs(cum_p - cum_a)

    return round(float(emd), 6)
