"""Idempotent staging -> warehouse load: upsert dimensions, then facts.

Every dimension is upserted on its natural key (`ON CONFLICT ... DO UPDATE`)
so re-running the pipeline updates existing rows in place instead of
duplicating them, then re-read to resolve the surrogate keys facts need.
Rows are chunked to keep a single INSERT statement's parameter count sane.
"""

from __future__ import annotations

import pandas as pd
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
    """Populate warehouse.dim_date for every date observed in sales_lines (+/- 1 day buffer)."""
    valid_dates = sales_lines["order_date"].dropna()
    if valid_dates.empty:
        return
    dim_date = build_dim_date(valid_dates.min(), valid_dates.max())
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
    rows = products.to_dict("records")
    _upsert(
        conn,
        "warehouse",
        "dim_product",
        rows,
        conflict_columns=["product_source_id"],
        update_columns=["product_name", "category", "unit_price"],
    )
    return _select_key_map(conn, "warehouse", "dim_product", "product_key", "product_source_id")


def upsert_dim_customer(
    conn: Connection, sales_lines: pd.DataFrame, location_keys: dict[str, int]
) -> dict[str, int]:
    """Upsert one dim_customer row per distinct customer_source_id. Returns {customer_source_id: customer_key}."""
    customers = sales_lines.drop_duplicates("customer_source_id", keep="last")[
        ["customer_source_id", "region_source"]
    ].copy()
    customers["location_key"] = customers["region_source"].map(location_keys)
    rows = customers[["customer_source_id", "location_key"]].to_dict("records")
    _upsert(
        conn,
        "warehouse",
        "dim_customer",
        rows,
        conflict_columns=["customer_source_id"],
        update_columns=["location_key"],
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
            "standard_lead_time_days": None,
        }
        for dept in departments
    ]
    _upsert(
        conn,
        "warehouse",
        "dim_supplier",
        rows,
        conflict_columns=["supplier_source_id"],
        update_columns=["supplier_name", "category"],
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


def upsert_fact_sales(
    conn: Connection,
    sales_lines: pd.DataFrame,
    product_keys: dict[str, int],
    customer_keys: dict[str, int],
    location_keys: dict[str, int],
) -> None:
    """Upsert fact_sales, one row per source order line item."""
    df = sales_lines.copy()
    df["date_key"] = df["order_date"].apply(date_key)
    df["product_key"] = df["product_source_id"].map(product_keys)
    df["customer_key"] = df["customer_source_id"].map(customer_keys)
    df["location_key"] = df["region_source"].map(location_keys)

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
            "quantity": int(r.quantity),
            "unit_price": float(r.unit_price_aed),
            "discount": 0,
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
            "quantity",
            "unit_price",
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
            "transport_cost": None,  # no cost column in DataCo — not fabricated, see plan
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
        ],
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

        upsert_fact_sales(conn, sales_lines, product_keys, customer_keys, location_keys)
        upsert_fact_shipments(conn, sales_lines, product_keys, supplier_keys, warehouse_keys)
    logger.info("load_warehouse_done", rows=len(sales_lines))
