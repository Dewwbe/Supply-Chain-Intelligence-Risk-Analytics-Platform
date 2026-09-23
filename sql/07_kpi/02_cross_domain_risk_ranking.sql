-- Business question: which suppliers combine low on-time delivery with high cost variability
-- — i.e. where should Procurement focus first?

WITH otd AS (
    SELECT
        fsh.supplier_key,
        COUNT(*) FILTER (
            WHERE fsh.actual_delivery_date_key <= fsh.expected_delivery_date_key
        )::NUMERIC / NULLIF(COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key IS NOT NULL), 0)
            AS on_time_rate
    FROM warehouse.fact_shipments fsh
    GROUP BY fsh.supplier_key
),
cost_variability AS (
    SELECT
        fpo.supplier_key,
        STDDEV(fpo.unit_cost) / NULLIF(AVG(fpo.unit_cost), 0) AS cost_variability
    FROM warehouse.fact_purchase_orders fpo
    GROUP BY fpo.supplier_key
)
SELECT
    ds.supplier_name,
    ROUND(otd.on_time_rate, 4) AS on_time_rate,
    ROUND(cost_variability.cost_variability, 4) AS cost_variability,
    RANK() OVER (ORDER BY otd.on_time_rate ASC) AS otd_risk_rank,
    RANK() OVER (ORDER BY cost_variability.cost_variability DESC) AS cost_risk_rank,
    CASE
        WHEN otd.on_time_rate < 0.7 AND cost_variability.cost_variability > 0.2 THEN 'High priority'
        WHEN otd.on_time_rate < 0.7 OR cost_variability.cost_variability > 0.2 THEN 'Monitor'
        ELSE 'Low risk'
    END AS procurement_priority
FROM otd
JOIN cost_variability ON cost_variability.supplier_key = otd.supplier_key
JOIN warehouse.dim_supplier ds ON ds.supplier_key = otd.supplier_key
ORDER BY otd_risk_rank, cost_risk_rank;
