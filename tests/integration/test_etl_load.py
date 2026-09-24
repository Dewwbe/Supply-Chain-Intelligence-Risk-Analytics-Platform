"""Integration test for etl/load — needs a running Postgres with the Phase 2
schema/seed applied (`make db-up && make migrate`). Skipped otherwise, per
docs/coding_standards.md ("integration tests use a disposable test
database").
"""

from __future__ import annotations

import pandas as pd
import pytest
from etl.load.warehouse import load_warehouse
from sqlalchemy import text
from src.common.db import get_engine


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


def _sample_sales_lines() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_system": ["olist", "dataco"],
            "order_id": ["o1", "d1"],
            "order_line_item_id": ["1", "1"],
            "order_date": pd.to_datetime(["2018-01-01", "2018-01-02"]),
            "customer_source_id": ["c1", "c2"],
            "product_source_id": ["p1", "p2"],
            "product_name": ["Test Product 1", "Test Product 2"],
            "product_category": ["Test Category", "Test Category"],
            "quantity": [1, 2],
            "unit_price_aed": [100.0, 50.0],
            "sales_amount_aed": [100.0, 100.0],
            "original_currency": ["BRL", "USD"],
            "original_amount": [101.0, 27.2],
            "region_source": ["olist:SP", "dataco:Southeast Asia"],
            "emirate": ["Dubai", "Sharjah"],
            "order_status": ["Delivered", "Completed"],
            "delivery_status": ["Shipping On Time", "Shipping On Time"],
            "shipping_mode": [None, "Standard Class"],
            "scheduled_ship_days": [None, 4],
            "real_ship_days": [None, 3],
            "source_department": [None, "Fitness"],
            "customer_segment": [None, "Consumer"],
            "discount_amount_aed": [0.0, 5.0],
        }
    )


def _cleanup(engine) -> None:
    """Remove this test's rows so a shared local dev database isn't left with
    permanent test residue (fact_sales.order_id 'o1'/'d1' don't collide with
    any real Olist/DataCo id, but there's no reason to leave them behind).
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM warehouse.fact_returns WHERE sales_key IN "
                "(SELECT sales_key FROM warehouse.fact_sales WHERE order_id IN ('o1', 'd1'))"
            )
        )
        conn.execute(text("DELETE FROM warehouse.fact_sales WHERE order_id IN ('o1', 'd1')"))
        conn.execute(
            text(
                "DELETE FROM warehouse.fact_purchase_orders WHERE po_source_id LIKE 'PO-DEPT-Fitness-p2-%'"
            )
        )


def test_load_warehouse_is_idempotent():
    sales_lines = _sample_sales_lines()
    engine = get_engine()

    try:
        load_warehouse(sales_lines)
        load_warehouse(sales_lines)  # second run must not duplicate rows

        with engine.connect() as conn:
            sales_count = conn.execute(
                text("SELECT COUNT(*) FROM warehouse.fact_sales WHERE order_id IN ('o1', 'd1')")
            ).scalar()
            po_count_after_2_runs = conn.execute(
                text("SELECT COUNT(*) FROM warehouse.fact_purchase_orders")
            ).scalar()

        load_warehouse(sales_lines)  # third run: synthetic tables must not duplicate either
        with engine.connect() as conn:
            po_count_after_3_runs = conn.execute(
                text("SELECT COUNT(*) FROM warehouse.fact_purchase_orders")
            ).scalar()

        assert sales_count == 2
        assert po_count_after_2_runs == po_count_after_3_runs
    finally:
        _cleanup(engine)
