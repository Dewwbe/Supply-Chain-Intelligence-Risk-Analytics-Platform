import numpy as np
import pandas as pd
import pytest
from src.anomaly_detection.detectors import (
    METHODS,
    detect_iqr,
    detect_isolation_forest,
    detect_zscore,
)

REQUIRED_COLUMNS = {"expected_value", "actual_value", "anomaly_score", "is_anomaly", "severity"}


def _series_with_one_outlier(n_normal: int = 30, outlier_value: float = 1000.0) -> pd.Series:
    rng = np.random.default_rng(0)
    normal = rng.normal(loc=50, scale=5, size=n_normal)
    values = np.append(normal, outlier_value)
    return pd.Series(values)


def _uniform_series(n: int = 30, value: float = 42.0) -> pd.Series:
    return pd.Series([value] * n)


@pytest.mark.parametrize("detector", METHODS.values())
def test_detector_output_has_required_columns(detector):
    result = detector(_series_with_one_outlier())
    assert REQUIRED_COLUMNS.issubset(result.columns)
    assert len(result) == 31


@pytest.mark.parametrize("detector", METHODS.values())
def test_detector_flags_the_obvious_outlier(detector):
    series = _series_with_one_outlier()
    result = detector(series)
    outlier_index = series.index[-1]
    assert result.loc[outlier_index, "is_anomaly"]
    assert result.loc[outlier_index, "severity"] in {"Low", "Medium", "High"}


@pytest.mark.parametrize("detector", METHODS.values())
def test_detector_anomaly_score_is_non_negative(detector):
    result = detector(_series_with_one_outlier())
    assert (result["anomaly_score"] >= 0).all()


@pytest.mark.parametrize("detector", METHODS.values())
def test_detector_severity_only_set_for_flagged_points(detector):
    result = detector(_series_with_one_outlier())
    non_anomalies = result[~result["is_anomaly"]]
    assert non_anomalies["severity"].isna().all()


def test_detect_iqr_uniform_data_has_no_anomalies():
    result = detect_iqr(_uniform_series())
    assert not result["is_anomaly"].any()


def test_detect_zscore_uniform_data_has_no_anomalies():
    result = detect_zscore(_uniform_series())
    assert not result["is_anomaly"].any()


def test_detect_isolation_forest_too_few_points_returns_no_anomalies():
    result = detect_isolation_forest(pd.Series([1.0, 2.0, 3.0]))
    assert not result["is_anomaly"].any()
    assert len(result) == 3


def test_detect_iqr_expected_value_is_median():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = detect_iqr(series)
    assert (result["expected_value"] == series.median()).all()


def test_detect_zscore_expected_value_is_mean():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = detect_zscore(series)
    assert (result["expected_value"] == series.mean()).all()
