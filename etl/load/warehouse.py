"""Idempotent staging -> warehouse load: upsert dimensions, then facts.

Every dimension is upserted on its natural key (`ON CONFLICT ... DO UPDATE`)
so re-running the pipeline updates existing rows in place instead of
duplicating them, then re-read to resolve the surrogate keys facts need.
Rows are chunked to keep a single INSERT statement's parameter count sane.
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.inventory import build_inventory
from etl.synthesize.product_cost import assign_unit_cost
from etl.synthesize.purchase_orders import build_purchase_orders
from etl.synthesize.returns import build_returns
from etl.synthesize.stores import assign_store, build_dim_store
from etl.synthesize.supplier_terms import assign_lead_time_days
from etl.synthesize.transport import assign_transport, build_dim_transport, estimate_transport_cost
from etl.transform.dates import build_dim_date, date_key
from etl.transform.master_data import EMIRATE_WEIGHTS
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine
from src.common.db import get_engine
from src.common.logging import get_logger

logger = get_logger(__name__)

_CHUNK = (
    2000  # keeps rows*columns under Postgres's 65535 bind-parameter limit for our widest tables
)

# Sentinel region_source values for the 5 per-emirate warehouse-hub locations
# (distinct from any real customer region_source, so they don't collide).
_WAREHOUSE_HUB_PREFIX = "__warehouse_hub__:"


def _chunks(rows: list[dict], size: int = _CHUNK) -> list[list[dict]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _upsert(
    conn: Connection,
    schema: str,
    table: str,
    rows: list[dict],
    conflict_columns: list[str],
    update_columns: list[str],
) -> None:
    if not rows:
        return
    metadata_table = _reflect(conn, schema, table)
    for chunk in _chunks(rows):
        stmt = pg_insert(metadata_table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={col: getattr(stmt.excluded, col) for col in update_columns},
        )
        conn.execute(stmt)
    logger.info("warehouse_upserted", table=f"{schema}.{table}", rows=len(rows))


def _reflect(conn: Connection, schema: str, table: str):
    from sqlalchemy import MetaData

    metadata = MetaData(schema=schema)
    metadata.reflect(bind=conn, schema=schema, only=[table])
    return metadata.tables[f"{schema}.{table}"]


def _select_key_map(
    conn: Connection, schema: str, table: str, key_col: str, natural_col: str
) -> dict:
    result = conn.execute(text(f"SELECT {natural_col}, {key_col} FROM {schema}.{table}"))
    return {row[0]: row[1] for row in result}


def upsert_dim_date(conn: Connection, sales_lines: pd.DataFrame) -> None:
    """Populate warehouse.dim_date for every date observed in sales_lines, plus a
    forward buffer covering the longest synthetic delay any downstream fact can
    add past an order date (purchase-order lead time + variance, return delay —
    see etl/synthesize/) so those FK lookups against dim_date never fall outside
    the populated range.
    """
    valid_dates = sales_lines["order_date"].dropna()
    if valid_dates.empty:
        return
    forward_buffer_days = 45
    dim_date = build_dim_date(
        valid_dates.min(), valid_dates.max() + pd.Timedelta(days=forward_buffer_days)
    )
    rows = dim_date.to_dict("records")
    _upsert(
        conn,
        "warehouse",
        "dim_date",
        rows,
        conflict_columns=["date_key"],
        update_columns=["is_uae_holiday", "season_label"],
    )


def upsert_ref_product_category(conn: Connection, sales_lines: pd.DataFrame) -> None:
    """Populate reference.ref_product_category from the categories actually observed.

    This is the one reference table that's data-driven rather than
    statically seeded (database/seed/) — see database/schema/00_reference_tables.sql.
    """
    grouped = (
        sales_lines.groupby("product_category")["source_system"]
        .agg(lambda s: "both" if s.nunique() > 1 else s.iloc[0])
        .reset_index()
    )
    rows = [
        {"category_name": r.product_category, "source_system": r.source_system}
        for r in grouped.itertuples()
    ]
    _upsert(
        conn,
        "reference",
        "ref_product_category",
        rows,
        conflict_columns=["category_name"],
        update_columns=["source_system"],
    )


def upsert_dim_location(conn: Connection, sales_lines: pd.DataFrame) -> dict[str, int]:
    """Upsert one dim_location row per distinct (emirate, region_source), plus 5 warehouse hubs.

    Returns a {region_source: location_key} map for downstream FK resolution.
    """
    customer_locations = (
        sales_lines[["emirate", "region_source"]].drop_duplicates().to_dict("records")
    )
    hub_locations = [
        {"emirate": emirate, "region_source": f"{_WAREHOUSE_HUB_PREFIX}{emirate}"}
        for emirate in EMIRATE_WEIGHTS
    ]
    rows = [{**r, "city": None} for r in customer_locations] + [
        {**r, "city": None} for r in hub_locations
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_location",
        rows,
        conflict_columns=["region_source"],
        update_columns=["emirate", "city"],
    )
    return _select_key_map(conn, "warehouse", "dim_location", "location_key", "region_source")


def upsert_dim_product(conn: Connection, sales_lines: pd.DataFrame) -> dict[str, int]:
    """Upsert one dim_product row per distinct product_source_id. Returns {product_source_id: product_key}."""
    products = (
        sales_lines.sort_values("order_date")
        .drop_duplicates("product_source_id", keep="last")[
            ["product_source_id", "product_name", "product_category", "unit_price_aed"]
        ]
        .rename(columns={"product_category": "category", "unit_price_aed": "unit_price"})
    )
    # unit_cost is SYNTHETIC (modelled from a category margin rate) — neither
    # source reports a wholesale price, see etl/synthesize/product_cost.py.
    products["unit_cost"] = products.apply(
        lambda r: assign_unit_cost(r.category, r.unit_price), axis=1
    )
    rows = products.to_dict("records")
    _upsert(
        conn,
        "warehouse",
        "dim_product",
        rows,
        conflict_columns=["product_source_id"],
        update_columns=["product_name", "category", "unit_price", "unit_cost"],
    )
    return _select_key_map(conn, "warehouse", "dim_product", "product_key", "product_source_id")


def upsert_dim_customer(
    conn: Connection, sales_lines: pd.DataFrame, location_keys: dict[str, int]
) -> dict[str, int]:
    """Upsert one dim_customer row per distinct customer_source_id. Returns {customer_source_id: customer_key}."""
    customers = sales_lines.drop_duplicates("customer_source_id", keep="last")[
        ["customer_source_id", "region_source", "customer_segment"]
    ].copy()
    customers["location_key"] = customers["region_source"].map(location_keys)
    rows = [
        {
            "customer_source_id": r.customer_source_id,
            "location_key": None if pd.isna(r.location_key) else int(r.location_key),
            "customer_segment": None if pd.isna(r.customer_segment) else r.customer_segment,
        }
        for r in customers.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_customer",
        rows,
        conflict_columns=["customer_source_id"],
        update_columns=["location_key", "customer_segment"],
    )
    return _select_key_map(conn, "warehouse", "dim_customer", "customer_key", "customer_source_id")


def upsert_dim_supplier(conn: Connection, sales_lines: pd.DataFrame) -> dict[str, int]:
    """Upsert one dim_supplier row per distinct DataCo department (see plan: DataCo has no
    real supplier entity, so its product departments are relabeled as suppliers, disclosed
    the same way as the emirate assignment). Returns {supplier_source_id: supplier_key}.
    """
    dataco = sales_lines[sales_lines["source_system"] == "dataco"]
    departments = dataco["source_department"].dropna().unique()
    rows = [
        {
            "supplier_source_id": f"DEPT-{dept}",
            "supplier_name": f"{dept} Supplier",
            "country": None,
            "category": dept,
            # SYNTHETIC — see etl/synthesize/supplier_terms.py.
            "standard_lead_time_days": assign_lead_time_days(f"DEPT-{dept}"),
        }
        for dept in departments
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_supplier",
        rows,
        conflict_columns=["supplier_source_id"],
        update_columns=["supplier_name", "category", "standard_lead_time_days"],
    )
    return _select_key_map(conn, "warehouse", "dim_supplier", "supplier_key", "supplier_source_id")


def upsert_dim_warehouse(conn: Connection, location_keys: dict[str, int]) -> dict[str, int]:
    """Upsert exactly 5 synthetic warehouses, one per emirate (see plan: warehouses.csv is
    already named SYNTHETIC in docs/data_dictionary.md). Returns {emirate: warehouse_key}.
    """
    rows = [
        {
            "warehouse_source_id": f"WH-{emirate.replace(' ', '_').upper()}",
            "warehouse_name": f"{emirate} Distribution Center",
            "location_key": location_keys[f"{_WAREHOUSE_HUB_PREFIX}{emirate}"],
            "capacity_units": None,
        }
        for emirate in EMIRATE_WEIGHTS
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_warehouse",
        rows,
        conflict_columns=["warehouse_source_id"],
        update_columns=["warehouse_name", "location_key"],
    )
    key_by_source = _select_key_map(
        conn, "warehouse", "dim_warehouse", "warehouse_key", "warehouse_source_id"
    )
    return {
        emirate: key_by_source[f"WH-{emirate.replace(' ', '_').upper()}"]
        for emirate in EMIRATE_WEIGHTS
    }


def upsert_dim_store(conn: Connection, location_keys: dict[str, int]) -> dict[str, int]:
    """Upsert the synthetic dim_store rows (see etl/synthesize/stores.py). Returns {store_source_id: store_key}."""
    stores = build_dim_store()
    rows = [
        {
            "store_source_id": r.store_source_id,
            "store_name": r.store_name,
            "store_type": r.store_type,
            "location_key": (
                None
                if pd.isna(r.emirate)
                else location_keys.get(f"{_WAREHOUSE_HUB_PREFIX}{r.emirate}")
            ),
        }
        for r in stores.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_store",
        rows,
        conflict_columns=["store_source_id"],
        update_columns=["store_name", "store_type", "location_key"],
    )
    return _select_key_map(conn, "warehouse", "dim_store", "store_key", "store_source_id")


def upsert_dim_transport(conn: Connection) -> tuple[dict[str, int], dict[str, float]]:
    """Upsert the synthetic dim_transport rows (see etl/synthesize/transport.py).

    Returns ({transport_source_id: transport_key}, {transport_source_id: avg_cost_per_km}).
    """
    transport = build_dim_transport()
    rows = transport.to_dict("records")
    _upsert(
        conn,
        "warehouse",
        "dim_transport",
        rows,
        conflict_columns=["transport_source_id"],
        update_columns=["mode_name", "carrier_name", "vehicle_type", "avg_cost_per_km"],
    )
    transport_keys = _select_key_map(
        conn, "warehouse", "dim_transport", "transport_key", "transport_source_id"
    )
    cost_per_km = dict(
        zip(transport["transport_source_id"], transport["avg_cost_per_km"], strict=True)
    )
    return transport_keys, cost_per_km


def upsert_fact_sales(
    conn: Connection,
    sales_lines: pd.DataFrame,
    product_keys: dict[str, int],
    customer_keys: dict[str, int],
    location_keys: dict[str, int],
    store_keys: dict[str, int],
) -> None:
    """Upsert fact_sales, one row per source order line item."""
    df = sales_lines.copy()
    df["date_key"] = df["order_date"].apply(date_key)
    df["product_key"] = df["product_source_id"].map(product_keys)
    df["customer_key"] = df["customer_source_id"].map(customer_keys)
    df["location_key"] = df["region_source"].map(location_keys)
    # store_key is SYNTHETIC channel attribution — see etl/synthesize/stores.py.
    natural_key = df["source_system"] + ":" + df["order_id"] + ":" + df["order_line_item_id"]
    df["store_source_id"] = [
        assign_store(k, emirate) for k, emirate in zip(natural_key, df["emirate"], strict=True)
    ]
    df["store_key"] = df["store_source_id"].map(store_keys)

    df = df.dropna(subset=["date_key", "product_key"])
    rows = [
        {
            "source_system": r.source_system,
            "order_id": r.order_id,
            "order_line_item_id": r.order_line_item_id,
            "date_key": int(r.date_key),
            "product_key": int(r.product_key),
            "customer_key": None if pd.isna(r.customer_key) else int(r.customer_key),
            "location_key": None if pd.isna(r.location_key) else int(r.location_key),
            "store_key": None if pd.isna(r.store_key) else int(r.store_key),
            "quantity": int(r.quantity),
            "unit_price": float(r.unit_price_aed),
            "discount": float(r.discount_amount_aed),
            "sales_amount": float(r.sales_amount_aed),
            "order_status": r.order_status,
            "delivery_status": r.delivery_status,
            "original_currency": r.original_currency,
            "original_sales_amount": float(r.original_amount),
        }
        for r in df.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "fact_sales",
        rows,
        conflict_columns=["source_system", "order_id", "order_line_item_id"],
        update_columns=[
            "date_key",
            "product_key",
            "customer_key",
            "location_key",
            "store_key",
            "quantity",
            "unit_price",
            "discount",
            "sales_amount",
            "order_status",
            "delivery_status",
            "original_currency",
            "original_sales_amount",
        ],
    )


def upsert_fact_shipments(
    conn: Connection,
    sales_lines: pd.DataFrame,
    product_keys: dict[str, int],
    supplier_keys: dict[str, int],
    warehouse_keys: dict[str, int],
    transport_keys: dict[str, int],
    transport_cost_per_km: dict[str, float],
) -> None:
    """Upsert fact_shipments from DataCo rows only (see plan: Olist lacks the
    scheduled/real shipping-day columns fact_shipments needs).
    """
    df = sales_lines[sales_lines["source_system"] == "dataco"].copy()
    scheduled_days = df["scheduled_ship_days"].astype(float).fillna(0)
    real_days = df["real_ship_days"].astype(float).fillna(0)
    df["order_date_key"] = df["order_date"].apply(date_key)
    df["expected_delivery_date_key"] = (
        df["order_date"] + pd.to_timedelta(scheduled_days, unit="D")
    ).apply(date_key)
    df["actual_delivery_date_key"] = (
        df["order_date"] + pd.to_timedelta(real_days, unit="D")
    ).apply(date_key)
    df["product_key"] = df["product_source_id"].map(product_keys)
    df["supplier_key"] = df["source_department"].apply(lambda d: supplier_keys.get(f"DEPT-{d}"))
    df["warehouse_key"] = df["emirate"].map(warehouse_keys)
    # transport_key/transport_cost are SYNTHETIC — see etl/synthesize/transport.py.
    df["transport_source_id"] = [
        assign_transport(key, mode)
        for key, mode in zip(df["order_line_item_id"], df["shipping_mode"], strict=True)
    ]
    df["transport_key"] = df["transport_source_id"].map(transport_keys)
    df["transport_cost"] = [
        (
            estimate_transport_cost(key, transport_cost_per_km[t])
            if t is not None and t in transport_cost_per_km
            else None
        )
        for key, t in zip(df["order_line_item_id"], df["transport_source_id"], strict=True)
    ]

    df = df.dropna(subset=["order_date_key", "product_key", "supplier_key", "warehouse_key"])
    rows = [
        {
            "source_system": r.source_system,
            "shipment_source_id": r.order_line_item_id,
            "supplier_key": int(r.supplier_key),
            "warehouse_key": int(r.warehouse_key),
            "product_key": int(r.product_key),
            "order_date_key": int(r.order_date_key),
            "expected_delivery_date_key": (
                None if pd.isna(r.expected_delivery_date_key) else int(r.expected_delivery_date_key)
            ),
            "actual_delivery_date_key": (
                None if pd.isna(r.actual_delivery_date_key) else int(r.actual_delivery_date_key)
            ),
            "quantity": int(r.quantity),
            "transport_mode": r.shipping_mode,
            "transport_key": None if pd.isna(r.transport_key) else int(r.transport_key),
            "transport_cost": None if pd.isna(r.transport_cost) else float(r.transport_cost),
        }
        for r in df.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "fact_shipments",
        rows,
        conflict_columns=["source_system", "shipment_source_id"],
        update_columns=[
            "supplier_key",
            "warehouse_key",
            "product_key",
            "order_date_key",
            "expected_delivery_date_key",
            "actual_delivery_date_key",
            "quantity",
            "transport_mode",
            "transport_key",
            "transport_cost",
        ],
    )


def upsert_fact_purchase_orders(
    conn: Connection,
    sales_lines: pd.DataFrame,
    supplier_keys: dict[str, int],
    product_keys: dict[str, int],
    warehouse_keys: dict[str, int],
) -> None:
    """Upsert the synthetic fact_purchase_orders rows (see etl/synthesize/purchase_orders.py)."""
    pos = build_purchase_orders(sales_lines)
    if pos.empty:
        return
    pos["supplier_key"] = pos["supplier_source_id"].map(supplier_keys)
    pos["product_key"] = pos["product_source_id"].map(product_keys)
    pos["warehouse_key"] = pos["emirate"].map(warehouse_keys)
    pos["order_date_key"] = pos["order_date"].apply(date_key)
    pos["expected_delivery_date_key"] = pos["expected_delivery_date"].apply(date_key)
    pos["actual_delivery_date_key"] = pos["actual_delivery_date"].apply(date_key)
    pos = pos.dropna(subset=["supplier_key", "product_key", "warehouse_key", "order_date_key"])

    rows = [
        {
            "po_source_id": r.po_source_id,
            "supplier_key": int(r.supplier_key),
            "warehouse_key": int(r.warehouse_key),
            "product_key": int(r.product_key),
            "order_date_key": int(r.order_date_key),
            "expected_delivery_date_key": (
                None if pd.isna(r.expected_delivery_date_key) else int(r.expected_delivery_date_key)
            ),
            "actual_delivery_date_key": (
                None if pd.isna(r.actual_delivery_date_key) else int(r.actual_delivery_date_key)
            ),
            "order_status": r.order_status,
            "quantity": int(r.quantity),
            "unit_cost": float(r.unit_cost),
            "total_cost": float(r.total_cost),
        }
        for r in pos.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "fact_purchase_orders",
        rows,
        conflict_columns=["po_source_id"],
        update_columns=[
            "supplier_key",
            "warehouse_key",
            "product_key",
            "order_date_key",
            "expected_delivery_date_key",
            "actual_delivery_date_key",
            "order_status",
            "quantity",
            "unit_cost",
            "total_cost",
        ],
    )


def upsert_fact_returns(conn: Connection, sales_lines: pd.DataFrame) -> None:
    """Upsert the synthetic fact_returns rows (see etl/synthesize/returns.py).

    Resolves sales_key by re-selecting fact_sales on its natural key, since
    returns must reference an already-upserted fact_sales row.
    """
    returns = build_returns(sales_lines)
    if returns.empty:
        return

    sales_key_rows = conn.execute(
        text(
            "SELECT source_system, order_id, order_line_item_id, sales_key "
            "FROM warehouse.fact_sales"
        )
    )
    sales_keys = {(r[0], r[1], r[2]): r[3] for r in sales_key_rows}

    returns["sales_key"] = [
        sales_keys.get((r.source_system, r.order_id, r.order_line_item_id))
        for r in returns.itertuples()
    ]
    returns["return_date_key"] = returns["return_date"].apply(date_key)
    returns = returns.dropna(subset=["sales_key", "return_date_key"])

    rows = [
        {
            "sales_key": int(r.sales_key),
            "return_date_key": int(r.return_date_key),
            "reason": r.reason,
            "returned_quantity": int(r.returned_quantity),
            "refund_amount": float(r.refund_amount),
        }
        for r in returns.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "fact_returns",
        rows,
        conflict_columns=["sales_key"],
        update_columns=["return_date_key", "reason", "returned_quantity", "refund_amount"],
    )


def upsert_fact_inventory(
    conn: Connection,
    sales_lines: pd.DataFrame,
    product_keys: dict[str, int],
    warehouse_keys: dict[str, int],
) -> None:
    """Upsert the synthetic fact_inventory rows (see etl/synthesize/inventory.py)."""
    inventory = build_inventory(sales_lines)
    if inventory.empty:
        return
    inventory["date_key"] = inventory["date"].apply(date_key)
    inventory["product_key"] = inventory["product_source_id"].map(product_keys)
    inventory["warehouse_key"] = inventory["warehouse_emirate"].map(warehouse_keys)
    inventory = inventory.dropna(subset=["date_key", "product_key", "warehouse_key"])

    rows = [
        {
            "date_key": int(r.date_key),
            "product_key": int(r.product_key),
            "warehouse_key": int(r.warehouse_key),
            "opening_stock": int(r.opening_stock),
            "received_quantity": int(r.received_quantity),
            "sold_quantity": int(r.sold_quantity),
            "closing_stock": int(r.closing_stock),
        }
        for r in inventory.itertuples()
    ]
    _upsert(
        conn,
        "warehouse",
        "fact_inventory",
        rows,
        conflict_columns=["product_key", "warehouse_key", "date_key"],
        update_columns=["opening_stock", "received_quantity", "sold_quantity", "closing_stock"],
    )


def load_warehouse(sales_lines: pd.DataFrame, engine: Engine | None = None) -> None:
    """Run every dimension upsert, then every fact upsert, in one transaction."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        upsert_dim_date(conn, sales_lines)
        upsert_ref_product_category(conn, sales_lines)
        location_keys = upsert_dim_location(conn, sales_lines)
        product_keys = upsert_dim_product(conn, sales_lines)
        customer_keys = upsert_dim_customer(conn, sales_lines, location_keys)
        supplier_keys = upsert_dim_supplier(conn, sales_lines)
        warehouse_keys = upsert_dim_warehouse(conn, location_keys)
        store_keys = upsert_dim_store(conn, location_keys)
        transport_keys, transport_cost_per_km = upsert_dim_transport(conn)

        upsert_fact_sales(conn, sales_lines, product_keys, customer_keys, location_keys, store_keys)
        upsert_fact_shipments(
            conn,
            sales_lines,
            product_keys,
            supplier_keys,
            warehouse_keys,
            transport_keys,
            transport_cost_per_km,
        )
        upsert_fact_purchase_orders(conn, sales_lines, supplier_keys, product_keys, warehouse_keys)
        upsert_fact_returns(conn, sales_lines)
        upsert_fact_inventory(conn, sales_lines, product_keys, warehouse_keys)
    logger.info("load_warehouse_done", rows=len(sales_lines))
