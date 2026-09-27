"""Anomalies as JSON-ready records (GET /api/v1/anomalies).

One domain at a time, so the API can cache each domain separately: a request
for `metric=daily_sales` never pays for the 180k-row transport-cost scan.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.anomaly_detection.data import DOMAINS
from src.anomaly_detection.pipeline import detect_domain

METRICS = tuple(DOMAINS)


def domain_anomalies(metric: str) -> list[dict[str, Any]]:
    """Every flagged point for one domain, highest anomaly score first."""
    flagged = detect_domain(metric).sort_values("anomaly_score", ascending=False)
    return [
        {
            "anomaly_id": row.anomaly_id,
            "date": pd.Timestamp(row.date).date().isoformat(),
            "entity": str(row.entity),
            "metric": row.metric,
            "method": row.method,
            "expected_value": round(float(row.expected_value), 4),
            "actual_value": round(float(row.actual_value), 4),
            "anomaly_score": round(float(row.anomaly_score), 4),
            "severity": str(row.severity),
        }
        for row in flagged.itertuples()
    ]
