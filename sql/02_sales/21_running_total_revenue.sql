-- Business question: what is the cumulative revenue trend to date, month over month?

WITH monthly_sales AS (
    SELECT
        dd.year,
        dd.month,
        SUM(fs.sales_amount) AS revenue
    FROM warehouse.fact_sales fs
    JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
    GROUP BY dd.year, dd.month
)
SELECT
    year,
    month,
    revenue,
    SUM(revenue) OVER (ORDER BY year, month) AS cumulative_revenue_aed
FROM monthly_sales
ORDER BY year, month;
