-- Business question: what does the monthly revenue trend look like?

SELECT
    dd.year,
    dd.month,
    SUM(fs.sales_amount) AS revenue_aed,
    COUNT(DISTINCT fs.order_id) AS order_count
FROM warehouse.fact_sales fs
JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;
