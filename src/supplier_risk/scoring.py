"""Interpretable, weighted supplier risk score (Phase 7).

Deliberately starts as a transparent weighted score rather than a black-box
model — see original spec §19: "Don't make the model unnecessarily
complicated." A classifier comparison (logistic regression / random forest /
XGBoost) is optional and only meaningful once a real historical target
(e.g. "supplier caused a stockout") exists — this project doesn't have one
(every input here is itself derived or synthetic; see
`notebooks/07_supplier_risk_scoring.ipynb` for why that rules out training a
classifier against it), so no ML comparison is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Weights sum to 1.0; documented here so they can be cited directly in the
# executive report rather than being implicit in code. Late delivery rate
# carries the most weight (the most direct reliability signal); average lead
# time and its variability are weighted separately, since a supplier can be
# slow-but-consistent or fast-but-erratic and those are different risks.
DEFAULT_WEIGHTS = {
    "late_delivery_rate": 0.25,
    "average_lead_time": 0.10,
    "lead_time_variability": 0.15,
    "defect_rate": 0.20,
    "cost_volatility": 0.15,
    "cancellation_rate": 0.15,
}

# Must match database/seed/06_ref_risk_level.sql exactly.
RISK_LEVEL_THRESHOLDS: list[tuple[float, str]] = [
    (25, "Low"),
    (50, "Medium"),
    (75, "High"),
]
RISK_LEVEL_DEFAULT = "Critical"


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
    """Min-max normalize a metric to 0-1 so weights are comparable.

    This makes every score relative to the *current* supplier set, not an
    absolute scale — disclosed, not hidden: adding or removing a supplier
    can shift everyone else's score even if their own metrics didn't change.
    """
    span = series.max() - series.min()
    if span == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.min()) / span


def _risk_level(score: float) -> str:
    """CASE score WHEN <25 THEN 'Low' WHEN <50 THEN 'Medium' WHEN <75 THEN 'High'
    ELSE 'Critical' — docs/kpi_dictionary.md §4, matching database/seed/06_ref_risk_level.sql.
    """
    for threshold, label in RISK_LEVEL_THRESHOLDS:
        if score < threshold:
            return label
    return RISK_LEVEL_DEFAULT


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
            "average_lead_time": _normalize(df["average_lead_time_days"]),
            "lead_time_variability": _normalize(df["lead_time_variability"]),
            "defect_rate": _normalize(df["defect_rate"]),
            "cost_volatility": _normalize(df["cost_variability"]),
            "cancellation_rate": _normalize(df["cancellation_rate"]),
        }
    )

    df["risk_score"] = sum(normalized[col] * w for col, w in weights.items()) * 100
    df["risk_level"] = df["risk_score"].apply(_risk_level)
    return df[["supplier_id", "risk_score", "risk_level"]].sort_values(
        "risk_score", ascending=False
    )
