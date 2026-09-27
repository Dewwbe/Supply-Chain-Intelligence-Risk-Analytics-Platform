"""Demand forecast endpoints.

Cached per (product, model, horizon): fitting SARIMA/ETS/XGBoost takes
seconds, and the history they fit on only changes after an ETL run.
Rate-limited at the *expensive* tier, because each new parameter combination
is a cache miss that fits a model — the cache alone can't stop a client from
iterating over products and models.
"""

from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import DEFAULT_LIMIT, EXPENSIVE_LIMIT, limiter
from src.forecasting.service import (
    InsufficientHistoryError,
    ProductNotFoundError,
    forecast_product,
    list_forecastable_products,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])
settings = get_settings()


class ForecastModel(str, Enum):
    seasonal_naive = "seasonal_naive"
    ets = "ets"
    sarima = "sarima"
    xgboost = "xgboost"


class ForecastPoint(BaseModel):
    week_ending: str
    forecast: float
    lower: float
    upper: float


class Forecast(BaseModel):
    product_id: str
    model: str
    season_length: int
    history_weeks: int
    last_observed_week: str
    confidence: float
    points: list[ForecastPoint]


class ForecastableProduct(BaseModel):
    product_id: str
    product_name: str
    total_quantity: int
    weeks_of_history: int


@router.get("", response_model=Forecast)
@limiter.limit(EXPENSIVE_LIMIT)
def forecast(
    request: Request,
    product_id: str = Query(description="product_source_id, see GET /forecast/products"),
    horizon: int = Query(default=12, ge=1, le=52, description="Weeks ahead"),
    model: ForecastModel = Query(default=ForecastModel.seasonal_naive),
) -> Forecast:
    """Weekly demand forecast with an 80% prediction interval. Seasonal Naive is
    the default because its intervals were the best calibrated in Phase 6.
    """
    key = f"forecast:{product_id}:{model.value}:{horizon}"
    try:
        data = get_cache().get_or_compute(
            key,
            settings.forecast_cache_ttl_seconds,
            lambda: forecast_product(product_id, horizon, model.value),
        )
    except ProductNotFoundError:
        raise HTTPException(404, f"No sales history for product '{product_id}'") from None
    except InsufficientHistoryError as exc:
        raise HTTPException(422, str(exc)) from None
    return Forecast(**data)


@router.get("/products", response_model=list[ForecastableProduct])
@limiter.limit(DEFAULT_LIMIT)
def forecastable_products(
    request: Request, limit: int = Query(default=10, ge=1, le=50)
) -> list[ForecastableProduct]:
    """Highest-volume products with at least 100 weeks of history."""
    data = get_cache().get_or_compute(
        f"forecast:products:{limit}",
        settings.forecast_cache_ttl_seconds,
        lambda: list_forecastable_products(limit),
    )
    return [ForecastableProduct(**p) for p in data]
