"""Throttled HTTP client for outbound calls to external, rate-limited APIs.

Used only in `etl/extract/uae_open_data.py` when pulling from the UAE Open
Data portal, to respect its fair-use limits. Not used for reading local
files (Olist/DataCo/M5 are downloaded once, not polled), so it is not
imported anywhere else in the codebase.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.api.core.config import get_settings


class ThrottledClient:
    """A simple token-bucket-throttled wrapper around httpx.Client."""

    def __init__(self, requests_per_second: float | None = None) -> None:
        settings = get_settings()
        self._min_interval = 1.0 / (requests_per_second or settings.external_api_rate_per_second)
        self._last_call: float = 0.0
        self._client = httpx.Client(timeout=30.0)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET with a minimum spacing between requests."""
        elapsed = time.monotonic() - self._last_call
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        response = self._client.get(url, **kwargs)
        self._last_call = time.monotonic()
        response.raise_for_status()
        return response

    def close(self) -> None:
        self._client.close()
