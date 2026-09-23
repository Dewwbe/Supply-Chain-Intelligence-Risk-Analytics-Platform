-- Business question: which products have the fewest days of supply left at their current stock level
-- (average closing stock / average daily demand), ranked most-urgent first?

WITH product_stats AS (
    SELECT
        fi.product_key,
        AVG(fi.closing_stock) AS avg_closing_stock,
        AVG(fi.sold_quantity) AS avg_daily_demand
    FROM warehouse.fact_inventory fi
    GROUP BY fi.product_key
)
SELECT
    dp.product_name,
    ROUND(product_stats.avg_closing_stock, 1) AS avg_closing_stock,
    ROUND(product_stats.avg_daily_demand, 2) AS avg_daily_demand,
    ROUND(product_stats.avg_closing_stock / NULLIF(product_stats.avg_daily_demand, 0), 1) AS days_of_supply,
    RANK() OVER (
        ORDER BY product_stats.avg_closing_stock / NULLIF(product_stats.avg_daily_demand, 0) ASC
    ) AS urgency_rank
FROM product_stats
JOIN warehouse.dim_product dp ON dp.product_key = product_stats.product_key
WHERE product_stats.avg_daily_demand > 0
ORDER BY urgency_rank;
