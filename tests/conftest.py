"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.core.cache import clear_memory_cache
from src.api.main import app
from src.api.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _isolate_api_state() -> Iterator[None]:
    """Every test starts with an empty cache and fresh rate-limit counters, so
    one test's cached value or request count can't leak into the next."""
    clear_memory_cache()
    limiter.reset()
    yield
    clear_memory_cache()
    limiter.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
