"""Minimal TTL cache used only for endpoints where recompute is expensive
and the underlying data changes far less often than it's read
(KPI + forecast endpoints — see README "Software layer" for the rationale).

Two backends are supported behind one interface so local dev doesn't need
Redis running, but production can flip `CACHE_BACKEND=redis` without any
route code changing.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.api.core.config import get_settings

if TYPE_CHECKING:
    import redis as redis_module

_memory_store: dict[str, tuple[float, Any]] = {}


class Cache:
    """Get/set with TTL, backed by an in-process dict or Redis."""

    def __init__(self) -> None:
        settings = get_settings()
        self._backend = settings.cache_backend
        self._redis: redis_module.Redis[bytes] | None = None
        if self._backend == "redis":
            import redis  # imported lazily so memory-backend dev doesn't need it

            self._redis = redis.Redis.from_url(settings.redis_url)

    def get(self, key: str) -> Any | None:
        if self._redis is not None:
            raw = cast("bytes | str | None", self._redis.get(key))
            return json.loads(raw) if raw is not None else None

        entry = _memory_store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            _memory_store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self._redis is not None:
            self._redis.set(key, json.dumps(value), ex=ttl_seconds)
            return
        _memory_store[key] = (time.time() + ttl_seconds, value)


_cache_singleton: Cache | None = None


def get_cache() -> Cache:
    """Return a process-wide Cache instance."""
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = Cache()
    return _cache_singleton
