-- Business question: how is revenue trending month over month, and what's
-- the absolute + percentage change vs the prior month?

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
    LAG(revenue) OVER (ORDER BY year, month) AS previous_month_revenue,
    revenue - LAG(revenue) OVER (ORDER BY year, month) AS revenue_change,
    ROUND(
        100.0 * (revenue - LAG(revenue) OVER (ORDER BY year, month))
            / NULLIF(LAG(revenue) OVER (ORDER BY year, month), 0),
        2
    ) AS revenue_change_pct
FROM monthly_sales
ORDER BY year, month;
