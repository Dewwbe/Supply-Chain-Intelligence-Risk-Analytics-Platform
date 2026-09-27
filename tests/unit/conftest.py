"""Unit-test fixtures: the API runs with no database behind it."""

from collections.abc import Iterator

import pytest
from src.api.core.dependencies import require_loaded_warehouse
from src.api.main import app


@pytest.fixture(autouse=True)
def _bypass_warehouse_guard() -> Iterator[None]:
    """Unit tests stub the services, so there's no warehouse to check;
    tests of the guard itself re-enable it (see test_api.real_guard)."""
    app.dependency_overrides[require_loaded_warehouse] = lambda: None
    yield
    app.dependency_overrides.pop(require_loaded_warehouse, None)
