"""Unit tests for CacheClient and cache_response decorator (Module 8)."""

from __future__ import annotations

import time
import pytest

from app.core.redis import CacheClient, cache_response


class TestCacheClient:
    def test_cache_set_and_get(self):
        client = CacheClient()
        client.set("test_key_1", {"data": 123}, expire_seconds=60)
        cached = client.get("test_key_1")
        assert cached == {"data": 123}

    def test_cache_expiration(self):
        client = CacheClient()
        client.set("test_exp_key", "value", expire_seconds=1)
        assert client.get("test_exp_key") == "value"
        time.sleep(1.1)
        assert client.get("test_exp_key") is None

    def test_cache_decorator(self):
        call_count = 0

        @cache_response(expire_seconds=10, key_prefix="test_dec")
        def sample_function(x: int) -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"result": x * 2}

        res1 = sample_function(5)
        res2 = sample_function(5)

        assert res1 == {"result": 10}
        assert res2 == {"result": 10}
        assert call_count == 1  # Function executed only once
