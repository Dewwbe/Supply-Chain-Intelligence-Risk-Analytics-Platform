"""Rate limiting for the public analytics endpoints.

Applied to `/api/v1/*` only (see README "Software layer" for why): those
routes sit in front of KPI/forecast recomputation and are not free to call
repeatedly. `/health` and docs routes are exempt so uptime checks and API
browsing are never throttled.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
)
