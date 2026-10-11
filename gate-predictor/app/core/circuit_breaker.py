"""LLM Circuit Breaker and Budget Cap.

Protects against LLM API vendor downtime, rate limits, or runaway API costs.
Transitions between CLOSED -> OPEN -> HALF_OPEN states based on consecutive failure threshold.
"""

from __future__ import annotations

import enum
import time
from typing import Any, Callable

from app.core.exceptions import LLMClientError
from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(str, enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(LLMClientError):
    """Raised when an execution call is blocked by an open circuit breaker."""


class CircuitBreaker:
    """Circuit breaker protecting external LLM API calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute call through circuit breaker protection."""
        now = time.time()

        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_timeout_seconds:
                logger.info("circuit_breaker_half_open_trial")
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning("circuit_breaker_blocked_call_is_open")
                raise CircuitBreakerOpenError(
                    "LLM service is currently unavailable (circuit breaker open)."
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self) -> None:
        """Reset state on successful call."""
        if self.state != CircuitState.CLOSED:
            logger.info("circuit_breaker_closed_recovered")
        self.state = CircuitState.CLOSED
        self.failure_count = 0

    def _on_failure(self) -> None:
        """Increment failure counter and trip circuit breaker if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                "circuit_breaker_tripped_open",
                consecutive_failures=self.failure_count,
            )


# Global circuit breaker instance
llm_circuit_breaker = CircuitBreaker()
