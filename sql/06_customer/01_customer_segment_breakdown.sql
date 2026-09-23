-- Business question: how does revenue break down across customer segments and channels?

SELECT
    COALESCE(dc.customer_segment, 'Unclassified') AS customer_segment,
    ds.store_type,
    COUNT(DISTINCT fs.customer_key) AS customer_count,
    SUM(fs.sales_amount) AS revenue_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_customer dc ON dc.customer_key = fs.customer_key
LEFT JOIN warehouse.dim_store ds ON ds.store_key = fs.store_key
GROUP BY COALESCE(dc.customer_segment, 'Unclassified'), ds.store_type
ORDER BY revenue_aed DESC;
