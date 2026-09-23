-- Business question: is a supplier's lead time trending up or down over recent shipments?
-- (5-shipment trailing moving average, per supplier)

WITH shipment_lead_times AS (
    SELECT
        fsh.supplier_key,
        order_date.full_date AS order_date,
        (actual_date.full_date - order_date.full_date) AS lead_time_days
    FROM warehouse.fact_shipments fsh
    JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
    JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
)
SELECT
    ds.supplier_name,
    shipment_lead_times.order_date,
    shipment_lead_times.lead_time_days,
    ROUND(
        AVG(shipment_lead_times.lead_time_days) OVER (
            PARTITION BY shipment_lead_times.supplier_key
            ORDER BY shipment_lead_times.order_date
            ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
        ),
        1
    ) AS moving_avg_lead_time_5
FROM shipment_lead_times
JOIN warehouse.dim_supplier ds ON ds.supplier_key = shipment_lead_times.supplier_key
ORDER BY ds.supplier_name, shipment_lead_times.order_date;
