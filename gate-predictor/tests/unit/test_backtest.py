"""Unit tests for backtesting framework (Module 4)."""

from __future__ import annotations

import pytest

from app.analytics.backtest import BacktestEngine
from app.analytics.predictor import QuestionRecord


@pytest.fixture
def sample_taxonomy() -> list[dict[str, str]]:
    return [
        {"id": "os_process_mgmt", "name": "Process Management", "code": "OS-PM"},
        {"id": "os_memory_mgmt", "name": "Memory Management", "code": "OS-MM"},
        {"id": "os_file_sys", "name": "File Systems", "code": "OS-FS"},
    ]


@pytest.fixture
def multi_year_records() -> list[QuestionRecord]:
    records = []
    # 2015 to 2024
    for y in range(2015, 2025):
        records.append(QuestionRecord(topic_id="os_process_mgmt", year=y, marks=5.0))
        records.append(QuestionRecord(topic_id="os_memory_mgmt", year=y, marks=3.0))
        if y % 2 == 0:
            records.append(QuestionRecord(topic_id="os_file_sys", year=y, marks=2.0))
    return records


class TestBacktestEngine:
    def test_run_backtest(self, sample_taxonomy, multi_year_records):
        backtester = BacktestEngine(eval_window_folds=3, history_window_years=5)
        report = backtester.run_backtest(
            subject_id="operating_systems",
            records=multi_year_records,
            taxonomy_topics=sample_taxonomy,
            eval_years=[2022, 2023, 2024],
        )

        assert report.subject_id == "operating_systems"
        assert len(report.folds) == 3
        assert "Predictor" in report.summary_by_model
        assert "Uniform" in report.summary_by_model

        # Ensure Predictor model has valid summary metrics
        stats = report.summary_by_model["Predictor"]
        assert "must_do_coverage_mean" in stats
        assert "spearman_correlation_mean" in stats

    def test_to_markdown_renders_table(self, sample_taxonomy, multi_year_records):
        backtester = BacktestEngine(eval_window_folds=2)
        report = backtester.run_backtest(
            subject_id="operating_systems",
            records=multi_year_records,
            taxonomy_topics=sample_taxonomy,
            eval_years=[2023, 2024],
        )

        md = report.to_markdown()
        assert "# GATE Topic Predictor - Backtest Evaluation Report" in md
        assert "| Model | Must-Do Coverage | Spearman rho |" in md
        assert "Predictor" in md
        assert "Disclaimer" in md
