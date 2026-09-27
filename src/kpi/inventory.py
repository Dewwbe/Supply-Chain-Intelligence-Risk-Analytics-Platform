"""Current inventory status per warehouse and network-wide (GET /api/v1/inventory).

Uses the same KPI definitions as `src/kpi/summary.py` and
docs/kpi_dictionary.md §2: stockout rate = share of product-days ending at
zero stock; fill rate = units fulfilled / units demanded (demand = real
fact_sales quantity for that product and day); inventory value = each
product's own latest closing stock at unit cost. Aggregation happens in
Postgres, so one query returns one row per warehouse, not 180k rows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from src.common.db import get_engine

_QUERY = """
WITH daily_demand AS (
    SELECT product_key, date_key, SUM(quantity) AS demand_quantity
    FROM warehouse.fact_sales
    GROUP BY product_key, date_key
),
latest AS (
    SELECT DISTINCT ON (fi.product_key)
        fi.product_key, fi.warehouse_key, fi.closing_stock,
        fi.closing_stock * dp.unit_cost AS stock_value
    FROM warehouse.fact_inventory fi
    JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
    JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
    ORDER BY fi.product_key, dd.full_date DESC
),
latest_by_warehouse AS (
    SELECT
        warehouse_key,
        SUM(stock_value) AS inventory_value,
        COUNT(*) FILTER (WHERE closing_stock = 0) AS products_out_of_stock
    FROM latest
    GROUP BY warehouse_key
)
SELECT
    dw.warehouse_name,
    COUNT(DISTINCT fi.product_key) AS products_tracked,
    COUNT(*) AS product_days,
    COUNT(*) FILTER (WHERE fi.closing_stock = 0) AS stockout_days,
    SUM(fi.sold_quantity) AS units_fulfilled,
    SUM(COALESCE(dem.demand_quantity, 0)) AS units_demanded,
    MAX(lw.inventory_value) AS inventory_value,
    MAX(lw.products_out_of_stock) AS products_out_of_stock
FROM warehouse.fact_inventory fi
JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
LEFT JOIN daily_demand dem
    ON dem.product_key = fi.product_key AND dem.date_key = fi.date_key
LEFT JOIN latest_by_warehouse lw ON lw.warehouse_key = fi.warehouse_key
GROUP BY dw.warehouse_name
ORDER BY dw.warehouse_name
"""


@dataclass
class InventoryStatus:
    warehouse: str
    products_tracked: int
    products_out_of_stock: int
    inventory_value_aed: float
    stockout_rate: float
    fill_rate: float


def _num(value: object) -> float:
    """SQL NULL arrives as None or NaN depending on the column dtype; both mean 0 here."""
    return 0.0 if pd.isna(value) else float(value)  # type: ignore[arg-type]


def _status(name: str, row: pd.Series) -> InventoryStatus:
    demanded = _num(row["units_demanded"])
    days = _num(row["product_days"])
    return InventoryStatus(
        warehouse=name,
        products_tracked=int(_num(row["products_tracked"])),
        products_out_of_stock=int(_num(row["products_out_of_stock"])),
        inventory_value_aed=round(_num(row["inventory_value"]), 2),
        stockout_rate=round(_num(row["stockout_days"]) / days, 4) if days else 0.0,
        fill_rate=round(_num(row["units_fulfilled"]) / demanded, 4) if demanded else 0.0,
    )


def compute_inventory_status() -> dict[str, Any]:
    """Network totals plus one entry per warehouse, as plain JSON-ready dicts."""
    by_warehouse = pd.read_sql_query(_QUERY, get_engine())
    network = _status("Network", by_warehouse.drop(columns="warehouse_name").sum())
    return {
        "network": asdict(network),
        "warehouses": [
            asdict(_status(row["warehouse_name"], row)) for _, row in by_warehouse.iterrows()
        ],
    }
