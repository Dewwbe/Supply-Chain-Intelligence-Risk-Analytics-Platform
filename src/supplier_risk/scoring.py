"""Interpretable, weighted supplier risk score (Phase 8 of the plan).

Deliberately starts as a transparent weighted score rather than a black-box
model — see original spec §19: "Don't make the model unnecessarily
complicated." A classifier comparison (logistic regression / random forest /
XGBoost) is optional and only meaningful once a historical target
(e.g. "supplier caused a stockout") exists.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Weights sum to 1.0; documented here so they can be cited directly in the
# executive report rather than being implicit in code.
DEFAULT_WEIGHTS = {
    "late_delivery_rate": 0.30,
    "lead_time_variability": 0.20,
    "defect_rate": 0.20,
    "cost_volatility": 0.15,
    "cancellation_rate": 0.15,
}


@dataclass
class SupplierRiskInputs:
    supplier_id: str
    on_time_rate: float  # 0-1
    average_lead_time_days: float
    lead_time_std_days: float
    defect_rate: float  # 0-1
    cost_variability: float  # coefficient of variation, 0-1+
    cancellation_rate: float  # 0-1


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a metric to 0-1 so weights are comparable."""
    span = series.max() - series.min()
    if span == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.min()) / span


def score_suppliers(
    inputs: list[SupplierRiskInputs], weights: dict[str, float] = DEFAULT_WEIGHTS
) -> pd.DataFrame:
    """Compute a 0-100 risk score per supplier from raw operational metrics."""
    df = pd.DataFrame([vars(i) for i in inputs])

    df["late_delivery_rate"] = 1 - df["on_time_rate"]
    df["lead_time_variability"] = df["lead_time_std_days"] / df["average_lead_time_days"].clip(
        lower=1e-6
    )

    normalized = pd.DataFrame(
        {
            "late_delivery_rate": _normalize(df["late_delivery_rate"]),
            "lead_time_variability": _normalize(df["lead_time_variability"]),
            "defect_rate": _normalize(df["defect_rate"]),
            "cost_volatility": _normalize(df["cost_variability"]),
            "cancellation_rate": _normalize(df["cancellation_rate"]),
        }
    )

    df["risk_score"] = sum(normalized[col] * w for col, w in weights.items()) * 100
    df["risk_level"] = pd.cut(
        df["risk_score"],
        bins=[-0.01, 25, 50, 75, 100],
        labels=["Low", "Medium", "High", "Critical"],
    )
    return df[["supplier_id", "risk_score", "risk_level"]].sort_values(
        "risk_score", ascending=False
    )
