-- Business question: for each month, what is revenue, its share of the running total,
-- and a simple performance label — a composite view combining CASE, FILTER, and window functions.

WITH monthly AS (
    SELECT
        dd.year,
        dd.month,
        SUM(fs.sales_amount) AS revenue_aed,
        COUNT(*) FILTER (WHERE fs.delivery_status = 'Late Delivery') AS late_deliveries,
        COUNT(*) AS total_lines
    FROM warehouse.fact_sales fs
    JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
    GROUP BY dd.year, dd.month
)
SELECT
    year,
    month,
    revenue_aed,
    ROUND(100.0 * revenue_aed / SUM(revenue_aed) OVER (), 2) AS pct_of_total_revenue,
    ROUND(100.0 * late_deliveries::NUMERIC / NULLIF(total_lines, 0), 2) AS late_delivery_pct,
    CASE
        WHEN late_deliveries::NUMERIC / NULLIF(total_lines, 0) > 0.15 THEN 'At risk'
        WHEN revenue_aed < AVG(revenue_aed) OVER () THEN 'Below average'
        ELSE 'Healthy'
    END AS month_status
FROM monthly
ORDER BY year, month;
