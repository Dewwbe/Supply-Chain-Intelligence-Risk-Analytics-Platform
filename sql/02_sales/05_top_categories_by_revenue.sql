-- Business question: which product categories drive the most revenue and margin?

SELECT
    dp.category,
    SUM(fs.sales_amount) AS revenue_aed,
    SUM(fs.sales_amount - (dp.unit_cost * fs.quantity)) AS gross_margin_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
GROUP BY dp.category
ORDER BY revenue_aed DESC;
