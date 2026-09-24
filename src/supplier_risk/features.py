"""Builds `SupplierRiskInputs` from the warehouse — the bridge between real
data and `scoring.py`'s pure scoring math.

Reuses `src/eda/data_access.py`'s loaders rather than re-querying the same
joins a third time (Phase 4 already built the shipment/PO/returns detail
pulls, including the defect-rate "quality proxy" join in
`load_returns_detail`'s `product_supplier` CTE).

Every feature here traces to a real or already-disclosed-synthetic source —
none of the six is fabricated fresh for scoring:

| Feature | Source |
|---|---|
| on_time_rate, average_lead_time_days, lead_time_std_days | real `fact_shipments` (DataCo) |
| defect_rate | synthetic `fact_returns.reason='Defective item'` proxy (Phase 4) |
| cost_variability | synthetic `fact_purchase_orders.unit_cost` (Phase 3) |
| cancellation_rate | synthetic `fact_purchase_orders.order_status='Cancelled'` (Phase 3) |
"""

from __future__ import annotations

import pandas as pd

from src.eda.data_access import (
    load_purchase_orders_detail,
    load_returns_detail,
    load_shipment_detail,
)
from src.supplier_risk.scoring import SupplierRiskInputs

DEFECT_REASON = "Defective item"


def compute_supplier_features(
    shipments: pd.DataFrame | None = None,
    purchase_orders: pd.DataFrame | None = None,
    returns: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per supplier with the 6 raw metrics `scoring.py` needs.

    Accepts already-loaded detail frames (so a notebook that already pulled
    them once doesn't re-query); loads from the warehouse otherwise.
    """
    shipments = shipments if shipments is not None else load_shipment_detail()
    purchase_orders = (
        purchase_orders if purchase_orders is not None else load_purchase_orders_detail()
    )
    returns = returns if returns is not None else load_returns_detail()

    shipment_stats = shipments.groupby("supplier_name").agg(
        shipment_count=("shipment_key", "count"),
        on_time_rate=("on_time", "mean"),
        average_lead_time_days=("actual_lead_time_days", "mean"),
        lead_time_std_days=("actual_lead_time_days", "std"),
    )

    po_stats = purchase_orders.groupby("supplier_name").agg(
        po_count=("po_key", "count"),
        cancellation_rate=("order_status", lambda s: (s == "Cancelled").mean()),
    )
    cost_variability = purchase_orders.groupby("supplier_name")["unit_cost"].agg(
        lambda s: s.std() / s.mean() if s.mean() else 0.0
    )
    po_stats["cost_variability"] = cost_variability

    shipped_by_supplier = shipments.groupby("supplier_name")["quantity"].sum()
    defective_by_supplier = (
        returns[returns["reason"] == DEFECT_REASON]
        .groupby("supplier_name")["returned_quantity"]
        .sum()
    )
    defect_rate = (defective_by_supplier / shipped_by_supplier).fillna(0.0).rename("defect_rate")

    features = shipment_stats.join(po_stats, how="outer").join(defect_rate, how="outer")
    features["lead_time_std_days"] = features["lead_time_std_days"].fillna(0.0)
    features = features.dropna(subset=["on_time_rate", "average_lead_time_days"])
    return features.reset_index()


def to_risk_inputs(features: pd.DataFrame) -> list[SupplierRiskInputs]:
    """Convert the features table into the dataclass list `scoring.score_suppliers` expects."""
    return [
        SupplierRiskInputs(
            supplier_id=row.supplier_name,
            on_time_rate=row.on_time_rate,
            average_lead_time_days=row.average_lead_time_days,
            lead_time_std_days=row.lead_time_std_days,
            defect_rate=row.defect_rate,
            cost_variability=row.cost_variability,
            cancellation_rate=row.cancellation_rate,
        )
        for row in features.itertuples()
    ]
