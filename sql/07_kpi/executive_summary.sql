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
-- Fill rate = units fulfilled / units demanded. Demand is the real
-- fact_sales quantity for that product and day (the demand the inventory
-- simulator was fed); fulfilled is fact_inventory.sold_quantity, which the
-- simulator caps at available stock. The shortfall is the unmet demand.
daily_demand AS (
    SELECT product_key, date_key, SUM(quantity) AS demand_quantity
    FROM warehouse.fact_sales
    GROUP BY product_key, date_key
),
fill AS (
    SELECT
        SUM(fi.sold_quantity)::NUMERIC
            / NULLIF(SUM(COALESCE(dd.demand_quantity, 0)), 0)
            AS fill_rate
    FROM warehouse.fact_inventory fi
    LEFT JOIN daily_demand dd
        ON dd.product_key = fi.product_key AND dd.date_key = fi.date_key
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
