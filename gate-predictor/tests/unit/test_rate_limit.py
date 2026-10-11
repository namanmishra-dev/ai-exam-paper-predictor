"""Unit tests for RateLimiter (Module 8)."""

from __future__ import annotations

import pytest

from app.core.rate_limit import RateLimiter


class TestRateLimiter:
    def test_rate_limiter_allows_under_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        allowed1, rem1 = limiter.is_allowed("user_1")
        allowed2, rem2 = limiter.is_allowed("user_1")
        allowed3, rem3 = limiter.is_allowed("user_1")

        assert allowed1 is True and rem1 == 2
        assert allowed2 is True and rem2 == 1
        assert allowed3 is True and rem3 == 0

    def test_rate_limiter_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.is_allowed("user_2")
        limiter.is_allowed("user_2")
        allowed3, rem3 = limiter.is_allowed("user_2")

        assert allowed3 is False
        assert rem3 == 0
