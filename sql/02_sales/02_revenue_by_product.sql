-- Business question: how much revenue has each product generated?

SELECT
    dp.product_source_id,
    dp.product_name,
    dp.category,
    SUM(fs.quantity) AS units_sold,
    SUM(fs.sales_amount) AS revenue_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
GROUP BY dp.product_source_id, dp.product_name, dp.category
ORDER BY revenue_aed DESC;
