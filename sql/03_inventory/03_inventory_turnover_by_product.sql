-- Business question: how quickly does each product turn over relative to its average stock?
-- (COGS / average inventory value — see docs/kpi_dictionary.md "Inventory Turnover")

WITH cogs AS (
    SELECT
        fs.product_key,
        SUM(fs.quantity * dp.unit_cost) AS total_cogs
    FROM warehouse.fact_sales fs
    JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
    GROUP BY fs.product_key
),
avg_inventory AS (
    SELECT
        fi.product_key,
        AVG((fi.opening_stock + fi.closing_stock) / 2.0 * dp.unit_cost) AS avg_inventory_value
    FROM warehouse.fact_inventory fi
    JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
    GROUP BY fi.product_key
)
SELECT
    dp.product_name,
    cogs.total_cogs,
    avg_inventory.avg_inventory_value,
    ROUND(cogs.total_cogs / NULLIF(avg_inventory.avg_inventory_value, 0), 2) AS inventory_turnover
FROM cogs
JOIN avg_inventory ON avg_inventory.product_key = cogs.product_key
JOIN warehouse.dim_product dp ON dp.product_key = cogs.product_key
ORDER BY inventory_turnover DESC;
