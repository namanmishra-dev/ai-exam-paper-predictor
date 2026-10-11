"""Unit tests for CircuitBreaker (Module 8)."""

from __future__ import annotations

import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


class TestCircuitBreaker:
    def test_circuit_breaker_normal_operation(self):
        cb = CircuitBreaker(failure_threshold=3)

        def mock_success():
            return "ok"

        res = cb.call(mock_success)
        assert res == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_trips_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60)

        def mock_fail():
            raise RuntimeError("Vendor error")

        # 1st failure
        with pytest.raises(RuntimeError):
            cb.call(mock_fail)
        assert cb.state == CircuitState.CLOSED

        # 2nd failure -> Trips OPEN
        with pytest.raises(RuntimeError):
            cb.call(mock_fail)
        assert cb.state == CircuitState.OPEN

        # Subsequent call blocked immediately with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(mock_fail)
