-- Business question: across the whole network, how many stockout-days occurred per month?

SELECT
    dd.year,
    dd.month,
    COUNT(*) AS inventory_days_tracked,
    COUNT(*) FILTER (WHERE fi.closing_stock = 0) AS stockout_days,
    ROUND(
        COUNT(*) FILTER (WHERE fi.closing_stock = 0)::NUMERIC / NULLIF(COUNT(*), 0),
        4
    ) AS stockout_rate
FROM warehouse.fact_inventory fi
JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;
