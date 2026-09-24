"""Forecast evaluation: MAE, RMSE, MAPE, WAPE, plus prediction-interval
coverage — formulas match docs/kpi_dictionary.md §5 exactly, so the
notebook and the dictionary never drift apart.

`compare_models` builds the one comparison table every model result must
appear in before any model may be called "best" (docs/implementation_plan.md:
"no model is declared winner before the evaluation table... is complete").
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.models import ForecastResult


def compute_metrics(actual: pd.Series, forecast: pd.Series) -> dict[str, float]:
    """MAE, RMSE, MAPE, WAPE for one (actual, forecast) pair, aligned by index."""
    actual, forecast = actual.align(forecast, join="inner")
    error = actual - forecast
    mae = error.abs().mean()
    rmse = np.sqrt((error**2).mean())
    # MAPE is unstable near zero actuals (docs/kpi_dictionary.md already flags
    # this) — reported alongside WAPE, never alone, and division-by-zero weeks
    # are excluded from MAPE specifically rather than producing inf.
    nonzero = actual != 0
    mape = (
        (error[nonzero].abs() / actual[nonzero].abs()).mean() * 100
        if nonzero.any()
        else float("nan")
    )
    wape = error.abs().sum() / actual.abs().sum() * 100 if actual.abs().sum() > 0 else float("nan")
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape, "WAPE": wape}


def compute_interval_coverage(actual: pd.Series, lower: pd.Series, upper: pd.Series) -> float:
    """Fraction of `actual` points that fall inside [lower, upper] — should be
    close to the model's stated confidence (e.g. ~0.8 for an 80% interval) if
    the interval is well calibrated; reported, not assumed.
    """
    actual, lower = actual.align(lower, join="inner")
    actual, upper = actual.align(upper, join="inner")
    return float(((actual >= lower) & (actual <= upper)).mean())


def compare_models(results: dict[str, ForecastResult], actual: pd.Series) -> pd.DataFrame:
    """One row per model: MAE/RMSE/MAPE/WAPE plus interval coverage/width.

    This table — not any single metric printed in isolation — is what a
    "winner" claim must be based on.
    """
    rows = []
    for name, result in results.items():
        metrics = compute_metrics(actual, result.point_forecast)
        rows.append(
            {
                "model": name,
                **metrics,
                "interval_coverage": compute_interval_coverage(actual, result.lower, result.upper),
                "avg_interval_width": (result.upper - result.lower).mean(),
            }
        )
    return pd.DataFrame(rows).set_index("model")
