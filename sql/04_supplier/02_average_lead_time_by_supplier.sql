-- Business question: what is each supplier's actual average lead time, vs. their stated standard?
-- (date_key is YYYYMMDD; join dim_date twice to get real DATE values before subtracting)

SELECT
    ds.supplier_name,
    ds.standard_lead_time_days,
    ROUND(AVG(actual_date.full_date - order_date.full_date), 1) AS avg_actual_lead_time_days,
    ROUND(STDDEV(actual_date.full_date - order_date.full_date), 1) AS lead_time_stddev_days
FROM warehouse.fact_shipments fsh
JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
WHERE fsh.actual_delivery_date_key IS NOT NULL
GROUP BY ds.supplier_name, ds.standard_lead_time_days
ORDER BY avg_actual_lead_time_days DESC;
