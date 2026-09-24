"""The 5 domains Phase 8 asks for, each reduced to the same
(date, entity, value) shape `pipeline.py` needs. Reuses `src/eda/data_access.py`'s
loaders rather than re-querying the same joins a third time.

Two domains are deliberately grouped by entity (`entity_is_group=True`):
`inventory_change` (per warehouse) and `supplier_lead_time` (per supplier) —
each entity has its own typical pattern, so a point should be judged
anomalous *relative to its own entity*, not the global population. The
other three are judged against one global population; `entity` there is
still attached to each row for labeling, it just isn't used to split the
detection itself.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from src.eda.data_access import load_inventory_detail, load_sales_detail, load_shipment_detail


def load_daily_sales() -> pd.DataFrame:
    """Network-wide daily total revenue. One population — a single bad day
    stands out against the whole history, not against itself."""
    sales = load_sales_detail()
    daily = sales.groupby("order_date")["sales_amount"].sum().reset_index()
    daily.columns = ["date", "value"]
    daily["entity"] = "Network"
    return daily[["date", "entity", "value"]]


def load_daily_inventory_change() -> pd.DataFrame:
    """Day-over-day change in total closing stock, per warehouse."""
    inventory = load_inventory_detail()
    daily_warehouse = (
        inventory.groupby(["warehouse_name", "date"])["closing_stock"].sum().reset_index()
    )
    daily_warehouse["value"] = daily_warehouse.groupby("warehouse_name")["closing_stock"].diff()
    daily_warehouse = daily_warehouse.dropna(subset=["value"])
    return daily_warehouse.rename(columns={"warehouse_name": "entity"})[["date", "entity", "value"]]


def load_shipment_delays() -> pd.DataFrame:
    """Per-shipment days late (actual - expected delivery date); negative = early.
    Judged against the whole shipment population, not per supplier — this is
    "how late is this shipment, full stop", distinct from `supplier_lead_time`
    below, which asks "is this unusual for *this* supplier specifically".
    """
    shipments = load_shipment_detail().dropna(
        subset=["actual_delivery_date", "expected_delivery_date"]
    )
    value = (shipments["actual_delivery_date"] - shipments["expected_delivery_date"]).dt.days
    return pd.DataFrame(
        {"date": shipments["order_date"], "entity": shipments["supplier_name"], "value": value}
    )


def load_transport_costs() -> pd.DataFrame:
    """Per-shipment transport cost, judged against the whole shipment population."""
    shipments = load_shipment_detail().dropna(subset=["transport_cost"])
    return pd.DataFrame(
        {
            "date": shipments["order_date"],
            "entity": shipments["carrier_name"],
            "value": shipments["transport_cost"],
        }
    )


def load_supplier_lead_times() -> pd.DataFrame:
    """Per-shipment actual lead time, grouped by supplier — a shipment unusual
    for *that supplier's* own typical lead time, not the network average."""
    shipments = load_shipment_detail().dropna(subset=["actual_lead_time_days"])
    return pd.DataFrame(
        {
            "date": shipments["order_date"],
            "entity": shipments["supplier_name"],
            "value": shipments["actual_lead_time_days"],
        }
    )


# metric name -> (loader, whether `entity` splits detection into separate populations)
DOMAINS: dict[str, tuple[Callable[[], pd.DataFrame], bool]] = {
    "daily_sales": (load_daily_sales, False),
    "inventory_change": (load_daily_inventory_change, True),
    "shipment_delay": (load_shipment_delays, False),
    "transport_cost": (load_transport_costs, False),
    "supplier_lead_time": (load_supplier_lead_times, True),
}
