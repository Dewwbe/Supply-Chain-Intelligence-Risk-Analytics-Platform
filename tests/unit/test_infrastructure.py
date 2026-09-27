"""Cache backends, outbound throttling, DB sessions and JSON logging."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
import redis
from src.api.core import cache as cache_module
from src.api.core.cache import Cache, clear_memory_cache
from src.common import db, http
from src.common.logging import configure_logging, get_logger

# --- cache --------------------------------------------------------------------------


def test_memory_cache_round_trip_and_ttl_expiry(monkeypatch):
    cache = Cache()
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
    cache.set("k", {"v": 1}, ttl_seconds=10)
    assert cache.get("k") == {"v": 1}
    now[0] += 11
    assert cache.get("k") is None
    assert cache.get("never-set") is None


def test_get_or_compute_only_computes_on_a_miss():
    cache = Cache()
    calls = []

    def compute():
        calls.append(1)
        return [1, 2]

    assert cache.get_or_compute("k", 60, compute) == [1, 2]
    assert cache.get_or_compute("k", 60, compute) == [1, 2]
    assert len(calls) == 1
    clear_memory_cache()
    cache.get_or_compute("k", 60, compute)
    assert len(calls) == 2


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    def _check(self):
        if self.fail:
            raise redis.ConnectionError("redis down")

    def get(self, key):
        self._check()
        return self.store.get(key)

    def set(self, key, value, ex):
        self._check()
        self.store[key] = value.encode()
        self.ttls[key] = ex

    def ping(self):
        self._check()
        return True


def _redis_cache(monkeypatch, fake: FakeRedis) -> Cache:
    settings = cache_module.get_settings()
    monkeypatch.setattr(settings, "cache_backend", "redis")
    monkeypatch.setattr(redis.Redis, "from_url", classmethod(lambda cls, url, **kw: fake))
    return Cache()


def test_redis_backend_stores_json_with_ttl(monkeypatch):
    fake = FakeRedis()
    cache = _redis_cache(monkeypatch, fake)
    cache.set("k", {"a": [1, 2]}, ttl_seconds=30)
    assert json.loads(fake.store["k"]) == {"a": [1, 2]}
    assert fake.ttls["k"] == 30
    assert cache.get("k") == {"a": [1, 2]}
    assert cache.backend == "redis" and cache.ping()


def test_redis_outage_degrades_to_recompute_not_failure(monkeypatch):
    cache = _redis_cache(monkeypatch, FakeRedis(fail=True))
    assert cache.get("k") is None
    cache.set("k", 1, ttl_seconds=30)  # must not raise
    assert cache.get_or_compute("k", 30, lambda: 42) == 42
    assert cache.ping() is False


def test_get_cache_is_a_singleton(monkeypatch):
    monkeypatch.setattr(cache_module, "_cache_singleton", None)
    assert cache_module.get_cache() is cache_module.get_cache()


# --- outbound throttling ----------------------------------------------------------------


def test_throttled_client_spaces_out_requests(monkeypatch):
    client = http.ThrottledClient(requests_per_second=2.0)  # >= 0.5s apart
    client._client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    clock = [100.0]
    sleeps: list[float] = []
    monkeypatch.setattr(http.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http.time, "sleep", sleeps.append)

    client.get("https://example.test/a")
    clock[0] += 0.1
    client.get("https://example.test/b")
    assert sleeps == [pytest.approx(0.4)]
    client.close()


def test_throttled_client_raises_on_http_errors():
    client = http.ThrottledClient(requests_per_second=1000)
    client._client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.test/")


# --- DB session scope ------------------------------------------------------------------------


class FakeSession:
    def __init__(self):
        self.events: list[str] = []

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")


def test_session_scope_commits_on_success_and_rolls_back_on_error(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(db, "_session_factory", lambda: lambda: session)

    with db.session_scope():
        pass
    assert session.events == ["commit", "close"]

    session.events.clear()
    with pytest.raises(RuntimeError), db.session_scope():
        raise RuntimeError("boom")
    assert session.events == ["rollback", "close"]


def test_engine_and_session_factory_use_configured_url(monkeypatch):
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()
    monkeypatch.setattr(db.get_settings(), "database_url", "sqlite://")
    try:
        assert str(db.get_engine().url) == "sqlite://"
        assert db._session_factory().kw["bind"] is db.get_engine()
    finally:
        db.get_engine.cache_clear()
        db._session_factory.cache_clear()


# --- logging -----------------------------------------------------------------------------


def test_structlog_and_stdlib_both_emit_one_json_object_per_line(capsys):
    configure_logging("INFO")
    get_logger("test.structlog").info("hello", answer=42)
    logging.getLogger("uvicorn.error").warning("from uvicorn")
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]

    assert lines[0]["event"] == "hello" and lines[0]["answer"] == 42
    assert lines[0]["level"] == "info" and "timestamp" in lines[0]
    assert lines[1]["event"] == "from uvicorn" and lines[1]["logger"] == "uvicorn.error"


def test_log_level_filters_lower_levels(capsys):
    configure_logging("WARNING")
    get_logger("test.level").info("hidden")
    get_logger("test.level").warning("shown")
    output = capsys.readouterr().out
    configure_logging("INFO")
    assert "hidden" not in output and "shown" in output
