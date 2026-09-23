-- Business question: how much capital is tied up in inventory, by warehouse emirate,
-- and what share of the network total does each represent?

WITH inventory_value AS (
    SELECT
        dw.location_key,
        SUM(fi.closing_stock * dp.unit_cost) AS inventory_value_aed
    FROM warehouse.fact_inventory fi
    JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
    JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
    GROUP BY dw.location_key
)
SELECT
    dl.emirate,
    inventory_value.inventory_value_aed,
    ROUND(
        100.0 * inventory_value.inventory_value_aed
            / SUM(inventory_value.inventory_value_aed) OVER (),
        2
    ) AS pct_of_network_value
FROM inventory_value
JOIN warehouse.dim_location dl ON dl.location_key = inventory_value.location_key
ORDER BY inventory_value.inventory_value_aed DESC;
