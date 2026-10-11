"""Locust Load Test Script.

Simulates 200 concurrent users accessing cached read endpoints:
- GET /api/v1/health
- GET /api/v1/subjects/operating_systems/topics/priority
- GET /api/v1/mock-papers/{id}

Target Performance SLA: Cached read endpoints p95 latency under 300 ms at 200 concurrent users.

Usage:
    locust -f loadtest/locustfile.py --host=http://localhost:8000 --users=200 --spawn-rate=20 --run-time=1m --headless
"""

from __future__ import annotations

import random
from locust import HttpUser, between, task


class GatePredictorUser(HttpUser):
    """Simulated GATE CS student user accessing cached endpoints."""

    wait_time = between(0.1, 0.5)  # High concurrency load generator pacing

    def on_start(self) -> None:
        """Fetch an active mock paper ID on user session start."""
        self.paper_id = "paper_default_demo"
        response = self.client.post(
            "/api/v1/mock-papers",
            json={"total_questions": 15, "total_marks": 25.0},
            name="/api/v1/mock-papers [Assembly]",
        )
        if response.status_code == 200:
            data = response.json()
            self.paper_id = data.get("paper_id", self.paper_id)

    @task(5)
    def test_get_topic_priorities(self) -> None:
        """Cached Read Endpoint 1: Topic Priority Scores & Buckets."""
        self.client.get(
            "/api/v1/subjects/operating_systems/topics/priority",
            name="/api/v1/subjects/{id}/topics/priority [Cached]",
        )

    @task(3)
    def test_get_mock_paper(self) -> None:
        """Cached Read Endpoint 2: Fetch Assembled Mock Paper Details."""
        self.client.get(
            f"/api/v1/mock-papers/{self.paper_id}",
            name="/api/v1/mock-papers/{id} [Cached]",
        )

    @task(2)
    def test_health_check(self) -> None:
        """Cached Read Endpoint 3: System Health Check."""
        self.client.get(
            "/api/v1/health",
            name="/api/v1/health",
        )
