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
        }
    )


def test_load_warehouse_is_idempotent():
    sales_lines = _sample_sales_lines()

    load_warehouse(sales_lines)
    load_warehouse(sales_lines)  # second run must not duplicate rows

    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM warehouse.fact_sales " "WHERE order_id IN ('o1', 'd1')")
        ).scalar()
    assert count == 2
