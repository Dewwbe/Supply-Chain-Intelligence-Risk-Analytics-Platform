-- Business question: how do suppliers rank against each other on on-time delivery rate?

WITH otd AS (
    SELECT
        ds.supplier_key,
        ds.supplier_name,
        COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key IS NOT NULL) AS delivered_shipments,
        COUNT(*) FILTER (
            WHERE fsh.actual_delivery_date_key <= fsh.expected_delivery_date_key
        )::NUMERIC / NULLIF(COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key IS NOT NULL), 0)
            AS on_time_rate
    FROM warehouse.fact_shipments fsh
    JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
    GROUP BY ds.supplier_key, ds.supplier_name
)
SELECT
    supplier_name,
    delivered_shipments,
    ROUND(on_time_rate, 4) AS on_time_rate,
    RANK() OVER (ORDER BY on_time_rate DESC) AS otd_rank,
    DENSE_RANK() OVER (ORDER BY on_time_rate DESC) AS otd_dense_rank
FROM otd
ORDER BY otd_rank;
