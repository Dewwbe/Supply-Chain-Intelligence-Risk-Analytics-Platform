import numpy as np
import pandas as pd
import pytest
from src.forecasting.evaluate import compare_models, compute_interval_coverage, compute_metrics
from src.forecasting.models import (
    ForecastResult,
    choose_season_length,
    forecast_ets,
    forecast_sarima,
    forecast_seasonal_naive,
    forecast_xgboost,
)
from src.forecasting.split import time_based_split


def _synthetic_weekly_series(n_weeks: int = 150, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2015-01-04", periods=n_weeks, freq="W")
    trend = np.linspace(50, 80, n_weeks)
    seasonal = 15 * np.sin(2 * np.pi * np.arange(n_weeks) / 52)
    noise = rng.normal(0, 3, n_weeks)
    values = np.clip(trend + seasonal + noise, 0, None)
    return pd.Series(values, index=index)


# --- split.py ----------------------------------------------------------------


def test_time_based_split_keeps_chronological_order():
    series = _synthetic_weekly_series(60)
    train, test = time_based_split(series, test_size=8)
    assert len(train) == 52
    assert len(test) == 8
    assert train.index[-1] < test.index[0]


def test_time_based_split_rejects_non_positive_test_size():
    series = _synthetic_weekly_series(20)
    with pytest.raises(ValueError):
        time_based_split(series, test_size=0)


def test_time_based_split_rejects_test_size_ge_length():
    series = _synthetic_weekly_series(20)
    with pytest.raises(ValueError):
        time_based_split(series, test_size=20)


# --- models.py -----------------------------------------------------------------


def test_choose_season_length_thresholds():
    assert choose_season_length(150) == 52
    assert choose_season_length(104) == 52
    assert choose_season_length(50) == 4
    assert choose_season_length(10) == 1


@pytest.fixture
def train_test():
    series = _synthetic_weekly_series(150)
    return time_based_split(series, test_size=8)


def _assert_valid_forecast(result: ForecastResult, horizon: int, future_index: pd.DatetimeIndex):
    assert len(result.point_forecast) == horizon
    assert list(result.point_forecast.index) == list(future_index)
    assert (result.lower <= result.point_forecast).all()
    assert (result.point_forecast <= result.upper).all()


def test_forecast_seasonal_naive_shape_and_interval_ordering(train_test):
    train, test = train_test
    result = forecast_seasonal_naive(train, horizon=len(test), season_length=52)
    _assert_valid_forecast(result, len(test), test.index)


def test_forecast_ets_shape_and_interval_ordering(train_test):
    train, test = train_test
    result = forecast_ets(train, horizon=len(test), season_length=52)
    _assert_valid_forecast(result, len(test), test.index)


def test_forecast_sarima_shape_and_interval_ordering(train_test):
    train, test = train_test
    result = forecast_sarima(train, horizon=len(test), season_length=52)
    _assert_valid_forecast(result, len(test), test.index)


def test_forecast_xgboost_shape_and_interval_ordering(train_test):
    train, test = train_test
    result = forecast_xgboost(train, horizon=len(test), season_length=52)
    _assert_valid_forecast(result, len(test), test.index)


def test_all_four_models_agree_on_future_index(train_test):
    train, test = train_test
    horizon = len(test)
    results = {
        "Seasonal Naive": forecast_seasonal_naive(train, horizon, 52),
        "ETS": forecast_ets(train, horizon, 52),
        "SARIMA": forecast_sarima(train, horizon, 52),
        "XGBoost": forecast_xgboost(train, horizon, 52),
    }
    indices = {tuple(r.point_forecast.index) for r in results.values()}
    assert len(indices) == 1
    assert tuple(test.index) in indices


# --- evaluate.py ---------------------------------------------------------------


def test_compute_metrics_zero_error_is_all_zero():
    actual = pd.Series([10.0, 20.0, 30.0], index=pd.date_range("2020-01-01", periods=3, freq="W"))
    metrics = compute_metrics(actual, actual.copy())
    assert metrics["MAE"] == 0
    assert metrics["RMSE"] == 0
    assert metrics["MAPE"] == 0
    assert metrics["WAPE"] == 0


def test_compute_metrics_matches_hand_calculation():
    idx = pd.date_range("2020-01-01", periods=2, freq="W")
    actual = pd.Series([100.0, 200.0], index=idx)
    forecast = pd.Series([90.0, 220.0], index=idx)
    metrics = compute_metrics(actual, forecast)
    assert metrics["MAE"] == pytest.approx((10 + 20) / 2)
    assert metrics["WAPE"] == pytest.approx((10 + 20) / 300 * 100)


def test_compute_interval_coverage_full_coverage():
    idx = pd.date_range("2020-01-01", periods=3, freq="W")
    actual = pd.Series([5.0, 5.0, 5.0], index=idx)
    lower = pd.Series([0.0, 0.0, 0.0], index=idx)
    upper = pd.Series([10.0, 10.0, 10.0], index=idx)
    assert compute_interval_coverage(actual, lower, upper) == 1.0


def test_compute_interval_coverage_partial():
    idx = pd.date_range("2020-01-01", periods=2, freq="W")
    actual = pd.Series([5.0, 50.0], index=idx)
    lower = pd.Series([0.0, 0.0], index=idx)
    upper = pd.Series([10.0, 10.0], index=idx)
    assert compute_interval_coverage(actual, lower, upper) == 0.5


def test_compare_models_returns_one_row_per_model_with_all_metrics(train_test):
    train, test = train_test
    horizon = len(test)
    results = {
        "Seasonal Naive": forecast_seasonal_naive(train, horizon, 52),
        "XGBoost": forecast_xgboost(train, horizon, 52),
    }
    table = compare_models(results, test)
    assert list(table.index) == ["Seasonal Naive", "XGBoost"]
    for col in ["MAE", "RMSE", "MAPE", "WAPE", "interval_coverage", "avg_interval_width"]:
        assert col in table.columns
