-- Business question: what are the average and lowest stock levels per product/warehouse?

SELECT
    dp.product_name,
    dw.warehouse_name,
    ROUND(AVG(fi.closing_stock), 1) AS avg_closing_stock,
    MIN(fi.closing_stock) AS min_closing_stock,
    MAX(fi.closing_stock) AS max_closing_stock
FROM warehouse.fact_inventory fi
JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
GROUP BY dp.product_name, dw.warehouse_name
ORDER BY avg_closing_stock ASC;
