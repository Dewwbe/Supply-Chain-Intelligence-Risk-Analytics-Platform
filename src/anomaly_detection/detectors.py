"""The three anomaly-detection methods, each returning the same per-point
shape (expected_value, actual_value, anomaly_score, is_anomaly, severity)
so `pipeline.py` can treat them identically — only the math differs.

`anomaly_score` is always non-negative with higher = more anomalous across
all three methods, even though the underlying scales are not comparable to
each other (an IQR distance of 2 and a Z-score of 2 don't mean the same
thing) — comparable *shape*, not comparable *scale*.

Severity thresholds are method-specific and documented inline, not implied
(docs/kpi_dictionary.md §6: "thresholds documented, not implied").
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

IQR_MULTIPLIER = 1.5
ZSCORE_THRESHOLD = 3.0
ISOLATION_FOREST_CONTAMINATION = 0.05  # a stated assumption (~5% of points), not discovered
ISOLATION_FOREST_RANDOM_STATE = 42


def _empty_result(values: pd.Series, expected: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "expected_value": expected,
            "actual_value": values,
            "anomaly_score": 0.0,
            "is_anomaly": False,
            "severity": pd.array([None] * len(values), dtype="object"),
        },
        index=values.index,
    )


def detect_iqr(values: pd.Series, k: float = IQR_MULTIPLIER) -> pd.DataFrame:
    """Flags points outside [Q1 - k*IQR, Q3 + k*IQR]. Score = distance beyond
    the nearest fence, in units of IQR. Severity (only for flagged points):
    <=0.5 IQR beyond the fence = Low, <=1.5 = Medium, >1.5 = High.
    """
    values = values.astype(float)
    median = values.median()
    expected = pd.Series(median, index=values.index)
    if len(values) < 4:
        return _empty_result(values, expected)

    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return _empty_result(values, expected)

    lower, upper = q1 - k * iqr, q3 + k * iqr
    distance = pd.Series(0.0, index=values.index)
    below, above = values < lower, values > upper
    distance[below] = (lower - values[below]) / iqr
    distance[above] = (values[above] - upper) / iqr
    is_anomaly = below | above

    severity = pd.Series(pd.array([None] * len(values), dtype="object"), index=values.index)
    flagged_distance = distance[is_anomaly]
    severity.loc[is_anomaly] = pd.cut(
        flagged_distance, bins=[-np.inf, 0.5, 1.5, np.inf], labels=["Low", "Medium", "High"]
    ).astype(object)

    return pd.DataFrame(
        {
            "expected_value": expected,
            "actual_value": values,
            "anomaly_score": distance,
            "is_anomaly": is_anomaly,
            "severity": severity,
        }
    )


def detect_zscore(values: pd.Series, threshold: float = ZSCORE_THRESHOLD) -> pd.DataFrame:
    """Flags points with |z| >= threshold. Score = |z|. Severity (only for
    flagged points): [threshold, threshold+1) = Low, [+1, +2) = Medium, >= +2 = High.
    """
    values = values.astype(float)
    mean, std = values.mean(), values.std()
    expected = pd.Series(mean, index=values.index)
    if len(values) < 4 or std == 0 or pd.isna(std):
        return _empty_result(values, expected)

    z = (values - mean) / std
    abs_z = z.abs()
    is_anomaly = abs_z >= threshold

    severity = pd.Series(pd.array([None] * len(values), dtype="object"), index=values.index)
    severity.loc[is_anomaly] = pd.cut(
        abs_z[is_anomaly],
        bins=[-np.inf, threshold + 1, threshold + 2, np.inf],
        labels=["Low", "Medium", "High"],
    ).astype(object)

    return pd.DataFrame(
        {
            "expected_value": expected,
            "actual_value": values,
            "anomaly_score": abs_z,
            "is_anomaly": is_anomaly,
            "severity": severity,
        }
    )


def detect_isolation_forest(
    values: pd.Series,
    contamination: float = ISOLATION_FOREST_CONTAMINATION,
    random_state: int = ISOLATION_FOREST_RANDOM_STATE,
) -> pd.DataFrame:
    """Flags points IsolationForest labels outlier (-1). Score = -score_samples
    (so higher = more anomalous, matching the other two methods' convention).
    Severity is a tercile split *within the flagged anomalies* — IsolationForest's
    score scale is data-dependent, unlike Z-score/IQR's fixed units, so severity
    here is relative rank among this run's anomalies, not an absolute cutoff.
    """
    values = values.astype(float)
    expected = pd.Series(values.median(), index=values.index)
    if len(values) < 10:
        return _empty_result(values, expected)

    x = values.to_numpy().reshape(-1, 1)
    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(x)
    score = pd.Series(-model.score_samples(x), index=values.index)
    is_anomaly = pd.Series(model.predict(x) == -1, index=values.index)

    severity = pd.Series(pd.array([None] * len(values), dtype="object"), index=values.index)
    flagged_scores = score[is_anomaly]
    if len(flagged_scores) >= 3 and flagged_scores.nunique() >= 3:
        severity.loc[is_anomaly] = pd.qcut(
            flagged_scores,
            q=[0, 1 / 3, 2 / 3, 1],
            labels=["Low", "Medium", "High"],
            duplicates="drop",
        ).astype(object)
    elif len(flagged_scores) > 0:
        severity.loc[is_anomaly] = "Medium"  # too few/uniform anomalies to rank into terciles

    return pd.DataFrame(
        {
            "expected_value": expected,
            "actual_value": values,
            "anomaly_score": score,
            "is_anomaly": is_anomaly,
            "severity": severity,
        }
    )


METHODS: dict[str, Callable[[pd.Series], pd.DataFrame]] = {
    "IQR": detect_iqr,
    "Z-Score": detect_zscore,
    "Isolation Forest": detect_isolation_forest,
}
