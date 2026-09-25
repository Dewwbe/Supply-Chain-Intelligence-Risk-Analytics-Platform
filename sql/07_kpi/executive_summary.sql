-- Business question: what are the current headline KPIs for the executive
-- dashboard (revenue, margin, stockout rate, fill rate, supplier OTD)?
-- Consumed by: src/api/routers/kpis.py::_compute_kpi_summary via
-- src/kpi/summary.py (Phase 10) — kept here as the reference query this
-- project's Python/DAX/Excel implementations all trace back to.
--
-- All-time totals, not filtered to "this year": the underlying data is a
-- static historical extract (Olist/DataCo, 2015-2018), so
-- `dd.year = EXTRACT(YEAR FROM CURRENT_DATE)` against today's real
-- calendar year would silently match zero rows — a bug this file
-- originally had, caught while building src/kpi/summary.py for Phase 10.

WITH revenue AS (
    SELECT SUM(sales_amount) AS revenue_aed
    FROM warehouse.fact_sales fs
),
margin AS (
    SELECT SUM(fs.sales_amount - (dp.unit_cost * fs.quantity)) AS gross_margin_aed
    FROM warehouse.fact_sales fs
    JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
),
stockouts AS (
    SELECT
        COUNT(*) FILTER (WHERE closing_stock = 0)::NUMERIC
            / NULLIF(COUNT(*), 0) AS stockout_rate
    FROM warehouse.fact_inventory
),
fill AS (
    SELECT
        SUM(sold_quantity)::NUMERIC
            / NULLIF(SUM(sold_quantity + GREATEST(0, opening_stock - closing_stock - received_quantity)), 0)
            AS fill_rate
    FROM warehouse.fact_inventory
),
otd AS (
    SELECT
        COUNT(*) FILTER (WHERE actual_delivery_date_key <= expected_delivery_date_key)::NUMERIC
            / NULLIF(COUNT(*) FILTER (WHERE actual_delivery_date_key IS NOT NULL), 0)
            AS supplier_otd
    FROM warehouse.fact_shipments
)
SELECT
    revenue.revenue_aed,
    margin.gross_margin_aed,
    stockouts.stockout_rate,
    fill.fill_rate,
    otd.supplier_otd
FROM revenue, margin, stockouts, fill, otd;
