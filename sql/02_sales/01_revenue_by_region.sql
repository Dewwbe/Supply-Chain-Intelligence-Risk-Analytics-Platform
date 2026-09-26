-- Business question: how much revenue has each emirate generated?

SELECT
    dl.emirate,
    COUNT(DISTINCT fs.order_id) AS order_count,
    SUM(fs.sales_amount) AS revenue_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_location dl ON dl.location_key = fs.location_key
GROUP BY dl.emirate
ORDER BY revenue_aed DESC;
