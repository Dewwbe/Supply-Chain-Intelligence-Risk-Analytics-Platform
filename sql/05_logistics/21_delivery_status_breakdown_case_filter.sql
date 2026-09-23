-- Business question: what fraction of shipments per warehouse are late vs. on-time vs. cancelled?

SELECT
    dw.warehouse_name,
    COUNT(*) AS total_shipments,
    COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key <= fsh.expected_delivery_date_key) AS on_time,
    COUNT(*) FILTER (
        WHERE fsh.actual_delivery_date_key > fsh.expected_delivery_date_key
    ) AS late,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key > fsh.expected_delivery_date_key)
            / NULLIF(COUNT(*), 0),
        2
    ) AS late_pct,
    CASE
        WHEN COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key > fsh.expected_delivery_date_key)::NUMERIC
            / NULLIF(COUNT(*), 0) > 0.25 THEN 'Needs attention'
        ELSE 'Healthy'
    END AS warehouse_health
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fsh.warehouse_key
GROUP BY dw.warehouse_name
ORDER BY late_pct DESC;
