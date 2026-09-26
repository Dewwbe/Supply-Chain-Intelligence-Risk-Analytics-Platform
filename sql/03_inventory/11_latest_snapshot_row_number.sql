-- Business question: what is the single latest stock snapshot for each product/warehouse?

WITH ranked AS (
    SELECT
        fi.product_key,
        fi.warehouse_key,
        fi.closing_stock,
        dd.full_date,
        ROW_NUMBER() OVER (
            PARTITION BY fi.product_key, fi.warehouse_key
            ORDER BY dd.full_date DESC
        ) AS row_num
    FROM warehouse.fact_inventory fi
    JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
)
SELECT
    dp.product_name,
    dw.warehouse_name,
    ranked.closing_stock,
    ranked.full_date AS as_of_date
FROM ranked
JOIN warehouse.dim_product dp ON dp.product_key = ranked.product_key
JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = ranked.warehouse_key
WHERE ranked.row_num = 1
ORDER BY ranked.closing_stock ASC;
