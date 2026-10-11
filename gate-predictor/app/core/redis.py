"""Redis Cache Abstraction with In-Memory Fallback.

Provides fast response caching for read endpoints (sub-300ms p95 latency target).
Falls back cleanly to an in-memory TTL dictionary when Redis server is offline.
"""

from __future__ import annotations

import json
import time
from functools import wraps
from typing import Any, Callable

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheClient:
    """Cache manager supporting Redis connection with automatic in-memory fallback."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.redis.redis_url
        self._redis: Any = None
        self._memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_timestamp)
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis server."""
        try:
            import redis
            self._redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("redis_connected", url=self.redis_url)
        except Exception as exc:
            logger.warning("redis_connection_failed_fallback_to_memory", error=str(exc))
            self._redis = None

    def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        if self._redis is not None:
            try:
                val = self._redis.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass

        # Memory cache fallback
        if key in self._memory_cache:
            val, exp = self._memory_cache[key]
            if time.time() < exp:
                return val
            del self._memory_cache[key]
        return None

    def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        """Set cached value with TTL in seconds."""
        if self._redis is not None:
            try:
                serialized = json.dumps(value)
                self._redis.setex(key, expire_seconds, serialized)
                return True
            except Exception:
                pass

        # Memory cache fallback
        self._memory_cache[key] = (value, time.time() + expire_seconds)
        return True

    def invalidate(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern."""
        count = 0
        if self._redis is not None:
            try:
                keys = self._redis.keys(pattern)
                if keys:
                    count = self._redis.delete(*keys)
                return count
            except Exception:
                pass

        # Memory cache cleanup
        keys_to_del = [k for k in self._memory_cache if pattern.replace("*", "") in k]
        for k in keys_to_del:
            del self._memory_cache[k]
            count += 1
        return count

    def clear(self) -> None:
        """Clear all cached keys."""
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        self._memory_cache.clear()


# Global cache client singleton
cache_client = CacheClient()


def cache_response(expire_seconds: int = 300, key_prefix: str = "api_cache") -> Callable:
    """Decorator to cache endpoint response dictionary/JSON by request path."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cached = cache_client.get(cache_key)
            if cached is not None:
                return cached

            res = func(*args, **kwargs)
            # Serialize Pydantic objects if returned
            serializable = res.model_dump() if hasattr(res, "model_dump") else res
            cache_client.set(cache_key, serializable, expire_seconds=expire_seconds)
            return res
        return wrapper
    return decorator
