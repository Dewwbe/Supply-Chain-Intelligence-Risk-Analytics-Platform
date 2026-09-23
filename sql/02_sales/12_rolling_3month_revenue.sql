-- Business question: what is the trailing 3-month rolling revenue trend?

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
    SUM(revenue) OVER (
        ORDER BY year, month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_3month_revenue
FROM monthly_sales
ORDER BY year, month;
