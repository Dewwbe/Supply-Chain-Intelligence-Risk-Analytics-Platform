"""TTL cache for the warehouse-backed read endpoints.

Used only where recompute is expensive and the underlying data changes far
less often than it's read: the warehouse refreshes once a day, while KPI,
supplier-risk, inventory, forecast and anomaly reads can arrive many times a
minute. Never used for `/scenario/simulate` results, which differ per request.

Two backends sit behind one interface, so local dev doesn't need Redis but a
multi-worker deployment can set `CACHE_BACKEND=redis` with no route changes.
A Redis outage degrades to recomputing, never to a failed request: the cache
is an optimisation, not a dependency.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from src.api.core.config import get_settings
from src.common.logging import get_logger

if TYPE_CHECKING:
    import redis as redis_module

logger = get_logger(__name__)
T = TypeVar("T")

_memory_store: dict[str, tuple[float, Any]] = {}


class Cache:
    """Get/set with TTL, backed by an in-process dict or Redis."""

    def __init__(self) -> None:
        settings = get_settings()
        self._backend = settings.cache_backend
        self._redis: redis_module.Redis[bytes] | None = None
        if self._backend == "redis":
            import redis  # imported lazily so memory-backend dev doesn't need it

            self._redis = redis.Redis.from_url(settings.redis_url, socket_timeout=2)

    @property
    def backend(self) -> str:
        return self._backend

    def get(self, key: str) -> Any | None:
        if self._redis is not None:
            import redis

            try:
                raw = cast("bytes | str | None", self._redis.get(key))
            except redis.RedisError as exc:
                logger.warning("cache_get_failed", key=key, error=str(exc))
                return None
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
            import redis

            try:
                self._redis.set(key, json.dumps(value), ex=ttl_seconds)
            except redis.RedisError as exc:
                logger.warning("cache_set_failed", key=key, error=str(exc))
            return
        _memory_store[key] = (time.time() + ttl_seconds, value)

    def get_or_compute(self, key: str, ttl_seconds: int, compute: Callable[[], T]) -> T:
        """Return the cached value for `key`, computing and storing it on a miss.

        `compute` must return something JSON-serialisable (plain dicts/lists),
        so both backends store and return exactly the same shape.
        """
        cached = self.get(key)
        if cached is not None:
            logger.debug("cache_hit", key=key)
            return cast(T, cached)
        logger.info("cache_miss", key=key)
        value = compute()
        self.set(key, value, ttl_seconds)
        return value

    def ping(self) -> bool:
        """True if the backend is usable (always true for the memory backend)."""
        if self._redis is None:
            return True
        import redis

        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False


_cache_singleton: Cache | None = None


def get_cache() -> Cache:
    """Return a process-wide Cache instance."""
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = Cache()
    return _cache_singleton


def clear_memory_cache() -> None:
    """Empty the in-process store (tests, and after a manual warehouse reload)."""
    _memory_store.clear()
