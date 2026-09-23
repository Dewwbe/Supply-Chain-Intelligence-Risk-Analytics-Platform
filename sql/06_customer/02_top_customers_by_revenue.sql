-- Business question: who are the top 20 customers by lifetime revenue?

SELECT
    dc.customer_source_id,
    dl.emirate,
    COUNT(DISTINCT fs.order_id) AS order_count,
    SUM(fs.sales_amount) AS lifetime_revenue_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_customer dc ON dc.customer_key = fs.customer_key
LEFT JOIN warehouse.dim_location dl ON dl.location_key = dc.location_key
GROUP BY dc.customer_source_id, dl.emirate
ORDER BY lifetime_revenue_aed DESC
LIMIT 20;
