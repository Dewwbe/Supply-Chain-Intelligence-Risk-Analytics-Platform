-- Business question: what share of total shipment volume does each transport mode carry?

SELECT
    fsh.transport_mode,
    SUM(fsh.quantity) AS total_units_shipped,
    ROUND(100.0 * SUM(fsh.quantity) / SUM(SUM(fsh.quantity)) OVER (), 2) AS pct_of_total_volume
FROM warehouse.fact_shipments fsh
GROUP BY fsh.transport_mode
ORDER BY total_units_shipped DESC;
