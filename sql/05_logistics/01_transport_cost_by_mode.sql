-- Business question: what is total and average transport cost by shipping mode?

SELECT
    fsh.transport_mode,
    COUNT(*) AS shipment_count,
    SUM(fsh.transport_cost) AS total_transport_cost_aed,
    ROUND(AVG(fsh.transport_cost), 2) AS avg_transport_cost_aed
FROM warehouse.fact_shipments fsh
WHERE fsh.transport_cost IS NOT NULL
GROUP BY fsh.transport_mode
ORDER BY total_transport_cost_aed DESC;
