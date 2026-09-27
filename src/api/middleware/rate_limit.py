"""Per-route rate limiting for the public analytics endpoints.

Routes opt in with `@limiter.limit(...)`; there is deliberately no global
default limit and no SlowAPIMiddleware, so `/health`, `/health/ready` and the
docs are never throttled (an uptime probe must not get a 429).

Two tiers, matched to what a burst of calls actually costs:
- `DEFAULT_LIMIT` for cached warehouse reads and the scenario calculator.
- `EXPENSIVE_LIMIT` for forecast and anomaly routes, where every distinct
  parameter combination is a cache miss that fits a model or scans the full
  history — the cache alone can't protect them from a client iterating
  parameters.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.core.config import get_settings

settings = get_settings()

DEFAULT_LIMIT = settings.rate_limit_default
EXPENSIVE_LIMIT = settings.rate_limit_expensive

limiter = Limiter(key_func=get_remote_address, headers_enabled=False)
