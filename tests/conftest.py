"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
