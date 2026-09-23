-- Business question: what share of each supplier's purchase orders get cancelled?

SELECT
    ds.supplier_name,
    COUNT(*) AS total_purchase_orders,
    COUNT(*) FILTER (WHERE fpo.order_status = 'Cancelled') AS cancelled_orders,
    ROUND(
        COUNT(*) FILTER (WHERE fpo.order_status = 'Cancelled')::NUMERIC / NULLIF(COUNT(*), 0),
        4
    ) AS cancellation_rate
FROM warehouse.fact_purchase_orders fpo
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fpo.supplier_key
GROUP BY ds.supplier_name
ORDER BY cancellation_rate DESC;
