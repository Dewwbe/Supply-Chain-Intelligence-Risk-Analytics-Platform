-- Business question: which 10 products generate the most revenue?

SELECT
    dp.product_source_id,
    dp.product_name,
    dp.category,
    SUM(fs.sales_amount) AS revenue_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
GROUP BY dp.product_source_id, dp.product_name, dp.category
ORDER BY revenue_aed DESC
LIMIT 10;
