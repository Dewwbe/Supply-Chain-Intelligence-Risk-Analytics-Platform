"""Forecast one product's weekly demand forward (GET /api/v1/forecast).

Fits the requested model on the product's *full* weekly history (Phase 6
held the last weeks out to compare models; serving a forecast uses all of
it) and returns the point forecast with its 80% prediction interval.
Seasonal Naive is the default: in notebooks/06 its WAPE was within 0.3
points of the best model and its intervals were the only ones close to
their stated 80% coverage (reports/executive_report §8, recommendation R4).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from src.forecasting import data
from src.forecasting.models import (
    ForecastResult,
    choose_season_length,
    forecast_ets,
    forecast_sarima,
    forecast_seasonal_naive,
    forecast_xgboost,
)

CONFIDENCE = 0.8
MIN_HISTORY_WEEKS = 8

MODELS: dict[str, Callable[..., ForecastResult]] = {
    "seasonal_naive": forecast_seasonal_naive,
    "ets": forecast_ets,
    "sarima": forecast_sarima,
    "xgboost": forecast_xgboost,
}


class ProductNotFoundError(LookupError):
    """No sales history exists for the requested product."""


class InsufficientHistoryError(ValueError):
    """The product has too little history to fit any model."""


def forecast_product(product_id: str, horizon: int, model: str) -> dict[str, Any]:
    """Return a JSON-ready forecast for one product."""
    weekly = data.load_weekly_demand(product_id)
    if weekly.empty:
        raise ProductNotFoundError(product_id)
    if len(weekly) < MIN_HISTORY_WEEKS:
        raise InsufficientHistoryError(
            f"{len(weekly)} weeks of history; at least {MIN_HISTORY_WEEKS} are needed"
        )

    season_length = choose_season_length(len(weekly))
    result = MODELS[model](weekly, horizon, season_length, confidence=CONFIDENCE)
    return {
        "product_id": product_id,
        "model": result.model_name,
        "season_length": season_length,
        "history_weeks": len(weekly),
        "last_observed_week": weekly.index[-1].date().isoformat(),
        "confidence": CONFIDENCE,
        "points": [
            {
                "week_ending": pd.Timestamp(week).date().isoformat(),
                "forecast": round(max(float(point), 0.0), 2),
                "lower": round(max(float(lower), 0.0), 2),
                "upper": round(max(float(upper), 0.0), 2),
            }
            for week, point, lower, upper in zip(
                result.point_forecast.index,
                result.point_forecast,
                result.lower,
                result.upper,
                strict=True,
            )
        ],
    }


def list_forecastable_products(n: int) -> list[dict[str, Any]]:
    """Top `n` products by volume with enough history for seasonal models."""
    products = data.select_top_products(n=n)
    return [
        {
            "product_id": str(row.product_source_id),
            "product_name": row.product_name,
            "total_quantity": int(row.total_quantity),
            "weeks_of_history": int(row.weeks_span),
        }
        for row in products.itertuples()
    ]
