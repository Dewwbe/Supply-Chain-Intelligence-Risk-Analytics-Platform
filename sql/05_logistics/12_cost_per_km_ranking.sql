-- Business question: how do transport options rank by their configured cost per km?

SELECT
    dt.mode_name,
    dt.carrier_name,
    dt.vehicle_type,
    dt.avg_cost_per_km,
    DENSE_RANK() OVER (ORDER BY dt.avg_cost_per_km DESC) AS cost_per_km_rank
FROM warehouse.dim_transport dt
ORDER BY cost_per_km_rank;
