"""The four forecasting models, each returning a point forecast plus a
prediction interval at the given confidence level (default 80%, per the
Phase 6 spec) — never a point forecast alone.

`choose_season_length` is a stated, disclosed adaptation to how much
history a product actually has: forcing an annual (52-week) seasonal
component onto a product with a year or less of history would just be
noise fit as signal, so shorter histories fall back to a shorter or no
seasonal period instead of silently using annual seasonality anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from scipy.stats import norm
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor


@dataclass
class ForecastResult:
    model_name: str
    point_forecast: pd.Series
    lower: pd.Series
    upper: pd.Series


def choose_season_length(n_train_weeks: int) -> int:
    """Annual (52), a short monthly-ish proxy (4), or none (1) — based on history length."""
    if n_train_weeks >= 104:
        return 52
    if n_train_weeks >= 16:
        return 4
    return 1


def _future_index(train: pd.Series, horizon: int) -> pd.DatetimeIndex:
    return pd.date_range(train.index[-1] + pd.Timedelta(weeks=1), periods=horizon, freq="W")


def forecast_seasonal_naive(
    train: pd.Series, horizon: int, season_length: int, confidence: float = 0.8
) -> ForecastResult:
    """forecast[h] = the value observed `season_length` weeks before it, repeating the
    last full seasonal cycle forward. Interval width grows with each additional
    seasonal cycle ahead, per Hyndman & Athanasopoulos's naive-method formula.
    """
    m = max(season_length, 1)
    last_cycle = train.iloc[-m:]
    values = [last_cycle.iloc[(h - 1) % m] for h in range(1, horizon + 1)]
    future_index = _future_index(train, horizon)
    point = pd.Series(values, index=future_index)

    residuals = train.diff(m).dropna() if m > 1 else train.diff(1).dropna()
    sigma = residuals.std()
    z = norm.ppf(0.5 + confidence / 2)
    sigma_h = pd.Series(
        [sigma * ((h - 1) // m + 1) ** 0.5 for h in range(1, horizon + 1)], index=future_index
    )
    return ForecastResult("Seasonal Naive", point, point - z * sigma_h, point + z * sigma_h)


def forecast_ets(
    train: pd.Series, horizon: int, season_length: int, confidence: float = 0.8
) -> ForecastResult:
    """Holt-Winters exponential smoothing via statsmodels' ETSModel (the API that
    supports prediction intervals, unlike the older ExponentialSmoothing class).
    """
    use_seasonal = season_length > 1 and len(train) >= 2 * season_length
    model = ETSModel(
        train,
        error="add",
        trend="add",
        damped_trend=True,
        seasonal="add" if use_seasonal else None,
        seasonal_periods=season_length if use_seasonal else None,
    )
    fit = model.fit(disp=False)
    pred = fit.get_prediction(start=len(train), end=len(train) + horizon - 1)
    summary = pred.summary_frame(alpha=1 - confidence)
    future_index = _future_index(train, horizon)
    return ForecastResult(
        "ETS",
        pd.Series(summary["mean"].to_numpy(), index=future_index),
        pd.Series(summary["pi_lower"].to_numpy(), index=future_index),
        pd.Series(summary["pi_upper"].to_numpy(), index=future_index),
    )


def forecast_sarima(
    train: pd.Series, horizon: int, season_length: int, confidence: float = 0.8
) -> ForecastResult:
    """SARIMA via statsmodels' SARIMAX, with native prediction intervals."""
    use_seasonal = season_length > 1 and len(train) >= 2 * season_length
    seasonal_order = (1, 1, 1, season_length) if use_seasonal else (0, 0, 0, 0)
    model = SARIMAX(
        train,
        order=(1, 1, 1),
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fit = model.fit(disp=False)
    forecast_obj = fit.get_forecast(steps=horizon)
    summary = forecast_obj.summary_frame(alpha=1 - confidence)
    future_index = _future_index(train, horizon)
    return ForecastResult(
        "SARIMA",
        pd.Series(summary["mean"].to_numpy(), index=future_index),
        pd.Series(summary["mean_ci_lower"].to_numpy(), index=future_index),
        pd.Series(summary["mean_ci_upper"].to_numpy(), index=future_index),
    )


def _lag_features(series: pd.Series, lags: list[int]) -> pd.DataFrame:
    df = pd.DataFrame({"y": series})
    for lag in lags:
        df[f"lag_{lag}"] = series.shift(lag)
    df["rolling_mean_4"] = series.shift(1).rolling(4).mean()
    df["week_of_year"] = series.index.isocalendar().week.to_numpy(dtype=int)
    df["month"] = series.index.month
    return df.dropna()


def forecast_xgboost(
    train: pd.Series, horizon: int, season_length: int, confidence: float = 0.8
) -> ForecastResult:
    """XGBoost on lag/calendar features, forecasting recursively (each step's
    prediction feeds the next step's lag features). Prediction intervals come
    from XGBoost's native multi-quantile objective (one model, three quantile
    outputs) rather than a separate interval technique, so the interval and
    point forecast are internally consistent.
    """
    lags = sorted({1, 2, 3, 4, season_length} - {0})
    feature_df = _lag_features(train, lags)
    feature_cols = [c for c in feature_df.columns if c != "y"]

    lower_q, upper_q = (1 - confidence) / 2, 1 - (1 - confidence) / 2
    model = XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=[lower_q, 0.5, upper_q],
        multi_strategy="one_output_per_tree",
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
    )
    model.fit(feature_df[feature_cols], feature_df["y"])

    history = train.copy()
    lowers, mids, uppers = [], [], []
    for _ in range(horizon):
        next_date = history.index[-1] + pd.Timedelta(weeks=1)
        row = {f"lag_{lag}": history.iloc[-lag] for lag in lags}
        row["rolling_mean_4"] = history.iloc[-4:].mean()
        row["week_of_year"] = next_date.isocalendar()[1]
        row["month"] = next_date.month
        x_next = pd.DataFrame([row])[feature_cols]
        q_low, q_mid, q_high = sorted(model.predict(x_next)[0])
        lowers.append(q_low)
        mids.append(q_mid)
        uppers.append(q_high)
        history.loc[next_date] = max(q_mid, 0.0)

    future_index = history.index[-horizon:]
    return ForecastResult(
        "XGBoost",
        pd.Series(mids, index=future_index),
        pd.Series(lowers, index=future_index),
        pd.Series(uppers, index=future_index),
    )
