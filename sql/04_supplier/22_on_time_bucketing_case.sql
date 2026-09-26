-- Business question: how many shipments per supplier fall into each delivery-performance bucket
-- (early, on-time, minor delay, major delay)?

SELECT
    ds.supplier_name,
    CASE
        WHEN fsh.actual_delivery_date_key IS NULL THEN 'Not yet delivered'
        WHEN actual_date.full_date < expected_date.full_date THEN 'Early'
        WHEN actual_date.full_date = expected_date.full_date THEN 'On time'
        WHEN actual_date.full_date - expected_date.full_date <= 2 THEN 'Minor delay (1-2 days)'
        ELSE 'Major delay (3+ days)'
    END AS performance_bucket,
    COUNT(*) AS shipment_count
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
JOIN warehouse.dim_date expected_date ON expected_date.date_key = fsh.expected_delivery_date_key
LEFT JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
GROUP BY ds.supplier_name, performance_bucket
ORDER BY ds.supplier_name, performance_bucket;
