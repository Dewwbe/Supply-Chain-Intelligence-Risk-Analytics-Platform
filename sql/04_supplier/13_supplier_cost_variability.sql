-- Business question: which suppliers have the most volatile unit costs across their purchase orders?

SELECT
    ds.supplier_name,
    ROUND(AVG(fpo.unit_cost), 2) AS avg_unit_cost,
    ROUND(STDDEV(fpo.unit_cost), 2) AS unit_cost_stddev,
    ROUND(STDDEV(fpo.unit_cost) / NULLIF(AVG(fpo.unit_cost), 0), 4) AS cost_variability
FROM warehouse.fact_purchase_orders fpo
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fpo.supplier_key
GROUP BY ds.supplier_name
ORDER BY cost_variability DESC;
