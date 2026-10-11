"""Rate limiting middleware and FastAPI dependency.

Implements a sliding window rate limiter per IP address or user session.
Exceeding the request limit raises HTTP 429 Too Many Requests.
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window in-memory & Redis rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check if request is allowed for client_id.

        Returns:
            Tuple of (is_allowed: bool, remaining_requests: int).
        """
        now = time.time()
        window_start = now - self.window_seconds

        if client_id not in self._requests:
            self._requests[client_id] = []

        # Filter out timestamps outside current sliding window
        timestamps = [t for t in self._requests[client_id] if t >= window_start]
        self._requests[client_id] = timestamps

        if len(timestamps) >= self.max_requests:
            remaining = 0
            return False, remaining

        self._requests[client_id].append(now)
        remaining = self.max_requests - len(self._requests[client_id])
        return True, remaining

    def reset(self) -> None:
        """Reset rate limiter state."""
        self._requests.clear()


# Global default rate limiter (100 requests per minute)
global_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware applying rate limits across incoming HTTP requests."""

    def __init__(
        self, app: Any, rate_limiter: RateLimiter | None = None
    ) -> None:
        super().__init__(app)
        self.limiter = rate_limiter or global_rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exempt health check and OpenAPI docs from rate limits
        if request.url.path in ("/api/v1/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        session_id = request.headers.get("X-Session-ID", client_ip)

        allowed, remaining = self.limiter.is_allowed(session_id)
        if not allowed:
            logger.warning("rate_limit_exceeded", client_ip=client_ip, session_id=session_id)
            raise HTTPException(
                status_code=429,
                detail="Too Many Requests. Please slow down and try again later.",
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
