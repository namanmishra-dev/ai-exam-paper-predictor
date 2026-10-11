"""Unit tests for evaluation metrics (Module 4)."""

from __future__ import annotations

import pytest

from app.analytics.metrics import (
    earth_movers_distance,
    expected_calibration_error,
    kl_divergence,
    must_do_coverage,
    precision_at_k,
    spearman_rank_correlation,
)


class TestMetrics:
    def test_spearman_perfect_positive_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]
        rho = spearman_rank_correlation(x, y)
        assert pytest.approx(rho, 0.001) == 1.0

    def test_spearman_perfect_negative_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [50.0, 40.0, 30.0, 20.0, 10.0]
        rho = spearman_rank_correlation(x, y)
        assert pytest.approx(rho, 0.001) == -1.0

    def test_precision_at_k(self):
        pred = {"t1": 0.9, "t2": 0.8, "t3": 0.7, "t4": 0.2}
        actual = {"t1": 10.0, "t2": 8.0, "t4": 5.0, "t3": 1.0}

        # Top 3 pred: t1, t2, t3. Top 3 actual: t1, t2, t4. Overlap: {t1, t2} (2/3)
        p3 = precision_at_k(pred, actual, k=3)
        assert pytest.approx(p3, 0.01) == 2 / 3

    def test_must_do_coverage(self):
        must_do = {"t1", "t2"}
        actual_marks = {"t1": 10.0, "t2": 5.0, "t3": 5.0}  # total 20

        cov = must_do_coverage(must_do, actual_marks)
        assert pytest.approx(cov, 0.01) == 15.0 / 20.0  # 75%

    def test_kl_divergence_identical_distributions(self):
        p = [0.5, 0.3, 0.2]
        q = [0.5, 0.3, 0.2]
        kl = kl_divergence(p, q)
        assert pytest.approx(kl, 0.01) == 0.0

    def test_ece_and_emd(self):
        p_pred = {"t1": 0.6, "t2": 0.4}
        p_act = {"t1": 0.5, "t2": 0.5}

        ece = expected_calibration_error(p_pred, p_act)
        emd = earth_movers_distance(p_pred, p_act)

        assert ece >= 0.0
        assert emd >= 0.0
