-- Business question: how does each product rank by revenue within its own category?

SELECT
    dp.category,
    dp.product_name,
    SUM(fs.sales_amount) AS revenue_aed,
    RANK() OVER (PARTITION BY dp.category ORDER BY SUM(fs.sales_amount) DESC) AS rank_in_category,
    DENSE_RANK() OVER (PARTITION BY dp.category ORDER BY SUM(fs.sales_amount) DESC) AS dense_rank_in_category
FROM warehouse.fact_sales fs
JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
GROUP BY dp.category, dp.product_name
ORDER BY dp.category, rank_in_category;
