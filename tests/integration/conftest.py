"""Skip integration tests whose infrastructure isn't available.

- `@pytest.mark.warehouse`: needs Postgres reachable *and* loaded
  (`make etl`) — an empty schema would fail these tests, not exercise them.
- `@pytest.mark.redis`: needs a Redis server at REDIS_URL (CI provides one).

Checked once per session, so a missing service costs one timeout, not one
per test.
"""

from __future__ import annotations

from functools import cache

import pytest
from sqlalchemy import text
from src.api.core.config import get_settings
from src.common.db import get_engine


@cache
def _warehouse_populated() -> bool:
    try:
        with get_engine().connect() as conn:
            return bool(
                conn.execute(text("SELECT EXISTS (SELECT 1 FROM warehouse.fact_sales)")).scalar()
            )
    except Exception:
        return False


@cache
def _redis_available() -> bool:
    try:
        import redis

        return bool(redis.Redis.from_url(get_settings().redis_url, socket_timeout=1).ping())
    except Exception:
        return False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker("warehouse") and not _warehouse_populated():
            item.add_marker(pytest.mark.skip(reason="populated warehouse not reachable"))
        if item.get_closest_marker("redis") and not _redis_available():
            item.add_marker(pytest.mark.skip(reason="Redis not reachable"))
