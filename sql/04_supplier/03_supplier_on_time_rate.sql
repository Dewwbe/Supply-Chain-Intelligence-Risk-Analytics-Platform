-- Business question: what percentage of each supplier's shipments arrive on or before
-- the expected delivery date (docs/kpi_dictionary.md "Supplier OTD")?

SELECT
    ds.supplier_name,
    COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key IS NOT NULL) AS delivered_shipments,
    COUNT(*) FILTER (
        WHERE fsh.actual_delivery_date_key <= fsh.expected_delivery_date_key
    ) AS on_time_shipments,
    ROUND(
        COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key <= fsh.expected_delivery_date_key)::NUMERIC
            / NULLIF(COUNT(*) FILTER (WHERE fsh.actual_delivery_date_key IS NOT NULL), 0),
        4
    ) AS on_time_delivery_rate
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
GROUP BY ds.supplier_name
ORDER BY on_time_delivery_rate DESC;
