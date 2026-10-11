"""Unit tests for Topic Predictor engine (Module 3)."""

from __future__ import annotations

import math
import pytest

from app.analytics.predictor import QuestionRecord, TopicPredictor
from app.db.models.subject import PriorityBucket


@pytest.fixture
def sample_taxonomy() -> list[dict[str, str]]:
    return [
        {"id": "os_process_mgmt", "name": "Process Management", "code": "OS-PM"},
        {"id": "os_memory_mgmt", "name": "Memory Management", "code": "OS-MM"},
        {"id": "os_file_sys", "name": "File Systems", "code": "OS-FS"},
        {"id": "os_deadlocks", "name": "Deadlocks", "code": "OS-DL"},
        {"id": "os_threads", "name": "Threads & Concurrency", "code": "OS-TH"},
    ]


@pytest.fixture
def sample_records() -> list[QuestionRecord]:
    records = []
    # Process management: high marks every year
    for y in range(2015, 2025):
        records.append(QuestionRecord(topic_id="os_process_mgmt", year=y, marks=6.0))

    # Memory management: recent upward trend
    for y in range(2020, 2025):
        records.append(QuestionRecord(topic_id="os_memory_mgmt", year=y, marks=float(y - 2018)))

    # Deadlocks: constant low marks
    for y in range(2015, 2025):
        if y % 2 == 0:
            records.append(QuestionRecord(topic_id="os_deadlocks", year=y, marks=2.0))

    # File Systems: old topic, disappeared after 2018
    for y in range(2015, 2019):
        records.append(QuestionRecord(topic_id="os_file_sys", year=y, marks=4.0))

    # Threads: rarely featured
    records.append(QuestionRecord(topic_id="os_threads", year=2024, marks=1.0))

    return records


class TestTopicPredictor:
    def test_predict_returns_valid_structure(self, sample_taxonomy, sample_records):
        predictor = TopicPredictor()
        res = predictor.predict(
            subject_id="operating_systems",
            subject_name="Operating Systems",
            records=sample_records,
            taxonomy_topics=sample_taxonomy,
            latest_year=2024,
        )

        assert res.subject_id == "operating_systems"
        assert res.disclaimer is not None
        assert len(res.all_topics) == len(sample_taxonomy)
        assert len(res.must_do_topics) > 0

    def test_must_do_high_yield_topics(self, sample_taxonomy, sample_records):
        predictor = TopicPredictor()
        res = predictor.predict(
            subject_id="operating_systems",
            subject_name="Operating Systems",
            records=sample_records,
            taxonomy_topics=sample_taxonomy,
            latest_year=2024,
        )

        must_do_ids = [t.topic_id for t in res.must_do_topics]
        assert "os_process_mgmt" in must_do_ids

    def test_empty_records_fallback(self, sample_taxonomy):
        predictor = TopicPredictor()
        res = predictor.predict(
            subject_id="operating_systems",
            subject_name="Operating Systems",
            records=[],
            taxonomy_topics=sample_taxonomy,
        )

        assert len(res.all_topics) == len(sample_taxonomy)
        for t in res.all_topics:
            assert t.priority_score == 0.5
            assert t.confidence == "low"

    def test_linear_slope_calculation(self):
        predictor = TopicPredictor()

        # Upward trend: marks equal to years
        years = [2020, 2021, 2022, 2023, 2024]
        marks = [1.0, 2.0, 3.0, 4.0, 5.0]
        slope = predictor._calculate_linear_slope(years, marks)
        assert pytest.approx(slope, 0.01) == 1.0

        # Flat trend
        marks_flat = [3.0, 3.0, 3.0, 3.0, 3.0]
        slope_flat = predictor._calculate_linear_slope(years, marks_flat)
        assert pytest.approx(slope_flat, 0.01) == 0.0

    def test_gap_score_capping(self):
        predictor = TopicPredictor()

        # Topic appeared long ago (2015), end_year is 2024 (9 year gap)
        gap_score, last_y = predictor._calculate_gap_score([2015], end_year=2024, window_years=10)
        assert last_y == 2015
        assert gap_score <= 1.5
