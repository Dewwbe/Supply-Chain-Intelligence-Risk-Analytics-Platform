"""Runs all 3 detectors over all 5 domains and assembles the required output
schema: anomaly_id, date, entity, metric, expected_value, actual_value,
anomaly_score, severity (docs/kpi_dictionary.md §6). `method` is added
beyond that literal list — with 3 methods run over the same data, omitting
which one flagged a given row would make the output ambiguous.
"""

from __future__ import annotations

import pandas as pd

from src.anomaly_detection.data import DOMAINS
from src.anomaly_detection.detectors import METHODS

OUTPUT_COLUMNS = [
    "anomaly_id",
    "date",
    "entity",
    "metric",
    "method",
    "expected_value",
    "actual_value",
    "anomaly_score",
    "severity",
]

MIN_GROUP_SIZE = 10  # below this, IQR/Z-score/Isolation Forest aren't meaningful


def _flagged_rows(
    values: pd.Series, dates: pd.Series, entities: pd.Series, metric: str
) -> pd.DataFrame:
    """Run every method in METHODS against one population, return only the
    rows each method actually flagged, in the unified output schema.
    """
    values = values.reset_index(drop=True)
    dates = dates.reset_index(drop=True)
    entities = entities.reset_index(drop=True)

    rows = []
    for method_name, detector in METHODS.items():
        result = detector(values)
        flagged = result[result["is_anomaly"]]
        for i in flagged.index:
            entity = entities.loc[i]
            date = dates.loc[i]
            rows.append(
                {
                    "anomaly_id": f"{metric}|{method_name}|{entity}|{date}|{i}",
                    "date": date,
                    "entity": entity,
                    "metric": metric,
                    "method": method_name,
                    "expected_value": flagged.loc[i, "expected_value"],
                    "actual_value": flagged.loc[i, "actual_value"],
                    "anomaly_score": flagged.loc[i, "anomaly_score"],
                    "severity": flagged.loc[i, "severity"],
                }
            )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def detect_domain(metric: str) -> pd.DataFrame:
    """Load one domain and run all 3 methods against it (grouped by entity
    first, for the 2 domains where that's the right population to compare
    against — see data.py's DOMAINS docstring).
    """
    loader, entity_is_group = DOMAINS[metric]
    df = loader()

    if not entity_is_group:
        return _flagged_rows(df["value"], df["date"], df["entity"], metric)

    frames = [
        _flagged_rows(group["value"], group["date"], group["entity"], metric)
        for _, group in df.groupby("entity")
        if len(group) >= MIN_GROUP_SIZE
    ]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def detect_all() -> pd.DataFrame:
    """Run every domain in DOMAINS and concatenate into one anomalies table."""
    frames = [detect_domain(metric) for metric in DOMAINS]
    return pd.concat(frames, ignore_index=True)
