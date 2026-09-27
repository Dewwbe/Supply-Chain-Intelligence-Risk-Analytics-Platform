"""The Redis cache backend against a real Redis server (CI runs one).

Unit tests cover the logic with a fake client; this proves the serialisation
and TTL behaviour hold against the real thing.
"""

import uuid

import pytest
from src.api.core import cache as cache_module
from src.api.core.cache import Cache

pytestmark = pytest.mark.redis


@pytest.fixture
def redis_cache(monkeypatch) -> Cache:
    monkeypatch.setattr(cache_module.get_settings(), "cache_backend", "redis")
    return Cache()


def test_round_trip_through_real_redis(redis_cache):
    key = f"test:{uuid.uuid4().hex}"
    payload = {"suppliers": [{"supplier": "A", "risk_score": 54.49}], "weights": {"x": 0.25}}
    redis_cache.set(key, payload, ttl_seconds=30)
    assert redis_cache.get(key) == payload
    assert redis_cache.ping()


def test_ttl_is_applied(redis_cache):
    key = f"test:{uuid.uuid4().hex}"
    redis_cache.set(key, 1, ttl_seconds=30)
    assert 0 < redis_cache._redis.ttl(key) <= 30  # type: ignore[union-attr]


def test_get_or_compute_shares_results_across_cache_instances(redis_cache, monkeypatch):
    # Two Cache objects stand in for two API workers: the second must reuse
    # the first's result — the reason to choose Redis over the memory backend.
    key = f"test:{uuid.uuid4().hex}"
    assert redis_cache.get_or_compute(key, 30, lambda: [1, 2, 3]) == [1, 2, 3]
    other_worker = Cache()
    assert other_worker.get_or_compute(key, 30, lambda: pytest.fail("recomputed")) == [1, 2, 3]
