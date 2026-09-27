"""Supplier risk report (GET /api/v1/suppliers/risk).

Joins each supplier's 0-100 score and level (`scoring.py`) with the raw
metrics behind it (`features.py`), so a caller can see *why* a supplier is
rated High — the same drivers the executive report's recommendation R5 cites.
"""

from __future__ import annotations

from typing import Any

from src.supplier_risk.features import compute_supplier_features, to_risk_inputs
from src.supplier_risk.scoring import DEFAULT_WEIGHTS, score_suppliers

FEATURE_COLUMNS = [
    "shipment_count",
    "on_time_rate",
    "average_lead_time_days",
    "lead_time_std_days",
    "po_count",
    "cancellation_rate",
    "cost_variability",
    "defect_rate",
]


def supplier_risk_report() -> dict[str, Any]:
    """Scores, levels and underlying metrics for every supplier, riskiest first."""
    features = compute_supplier_features()
    scores = score_suppliers(to_risk_inputs(features))
    merged = scores.merge(
        features.rename(columns={"supplier_name": "supplier_id"}), on="supplier_id"
    ).fillna(0)
    return {
        "weights": DEFAULT_WEIGHTS,
        "suppliers": [
            {
                "supplier": " ".join(str(row["supplier_id"]).split()),
                "risk_score": round(float(row["risk_score"]), 2),
                "risk_level": row["risk_level"],
                **{
                    col: (int(row[col]) if col.endswith("_count") else round(float(row[col]), 4))
                    for col in FEATURE_COLUMNS
                },
            }
            for _, row in merged.iterrows()
        ],
    }
