-- Business question: how many shipments has each supplier fulfilled, and what quantity/cost do they represent?

SELECT
    ds.supplier_name,
    COUNT(*) AS shipment_count,
    SUM(fsh.quantity) AS total_units_shipped,
    SUM(fsh.transport_cost) AS total_transport_cost_aed
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
GROUP BY ds.supplier_name
ORDER BY shipment_count DESC;
