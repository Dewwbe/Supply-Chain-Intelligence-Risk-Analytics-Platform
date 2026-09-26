-- Business question: which carriers are the most expensive on average, and how do they rank?

SELECT
    dt.carrier_name,
    dt.mode_name,
    COUNT(*) AS shipment_count,
    ROUND(AVG(fsh.transport_cost), 2) AS avg_transport_cost_aed,
    RANK() OVER (ORDER BY AVG(fsh.transport_cost) DESC) AS cost_rank
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_transport dt ON dt.transport_key = fsh.transport_key
GROUP BY dt.carrier_name, dt.mode_name
ORDER BY cost_rank;
