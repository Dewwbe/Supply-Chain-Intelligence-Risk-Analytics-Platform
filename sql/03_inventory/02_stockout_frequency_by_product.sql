-- Business question: how often does each product stock out (closing_stock = 0)?

SELECT
    dp.product_name,
    dw.warehouse_name,
    COUNT(*) AS days_tracked,
    COUNT(*) FILTER (WHERE fi.closing_stock = 0) AS stockout_days,
    ROUND(
        COUNT(*) FILTER (WHERE fi.closing_stock = 0)::NUMERIC / NULLIF(COUNT(*), 0),
        4
    ) AS stockout_rate
FROM warehouse.fact_inventory fi
JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
GROUP BY dp.product_name, dw.warehouse_name
HAVING COUNT(*) FILTER (WHERE fi.closing_stock = 0) > 0
ORDER BY stockout_rate DESC;
