"""Unit tests for FastAPI REST API v1 endpoints (Module 6 & 7)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAPIEndpoints:
    def test_health_check(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_topic_priorities(self, client):
        response = client.get("/api/v1/subjects/operating_systems/topics/priority")
        assert response.status_code == 200
        data = response.json()
        assert data["subject_id"] == "operating_systems"
        assert "disclaimer" in data
        assert len(data["must_do_topics"]) > 0

    def test_create_and_fetch_mock_paper(self, client):
        # Create mock paper
        create_resp = client.post(
            "/api/v1/mock-papers",
            json={"total_questions": 10, "total_marks": 15.0},
        )
        assert create_resp.status_code == 200
        paper_info = create_resp.json()
        paper_id = paper_info["paper_id"]
        assert paper_id.startswith("paper_")

        # Fetch paper
        fetch_resp = client.get(f"/api/v1/mock-papers/{paper_id}")
        assert fetch_resp.status_code == 200
        paper_data = fetch_resp.json()
        assert paper_data["id"] == paper_id
        assert len(paper_data["questions"]) > 0

    def test_submit_mock_paper_attempt(self, client):
        # Create mock paper
        create_resp = client.post(
            "/api/v1/mock-papers",
            json={"total_questions": 5, "total_marks": 10.0},
        )
        paper_id = create_resp.json()["paper_id"]

        # Submit attempt
        submit_payload = {
            "mock_paper_id": paper_id,
            "user_id": "test_student",
            "answers": [
                {"question_id": "cand_q_1", "user_answer": ["A"], "time_taken_seconds": 45.0},
            ],
        }

        submit_resp = client.post(f"/api/v1/mock-papers/{paper_id}/submit", json=submit_payload)
        assert submit_resp.status_code == 200
        report = submit_resp.json()
        assert report["mock_paper_id"] == paper_id
        assert "total_score" in report
        assert "topic_analytics" in report

    def test_get_job_status(self, client):
        response = client.get("/api/v1/jobs/job_test_123")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job_test_123"
        assert data["status"] == "completed"
