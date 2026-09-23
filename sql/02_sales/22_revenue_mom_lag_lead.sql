-- Business question: for each month, what were the prior and next month's revenue figures
-- (useful for spotting a one-off dip vs. a sustained decline)?

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
    LAG(revenue) OVER (ORDER BY year, month) AS previous_month_revenue,
    revenue AS current_month_revenue,
    LEAD(revenue) OVER (ORDER BY year, month) AS next_month_revenue
FROM monthly_sales
ORDER BY year, month;
