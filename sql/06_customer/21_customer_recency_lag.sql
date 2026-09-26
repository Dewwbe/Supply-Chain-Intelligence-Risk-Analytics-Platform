-- Business question: for repeat customers, how many days elapsed between consecutive orders?
-- (a building block for recency/churn analysis)

WITH customer_orders AS (
    SELECT DISTINCT
        fs.customer_key,
        fs.order_id,
        dd.full_date AS order_date
    FROM warehouse.fact_sales fs
    JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
)
SELECT
    dc.customer_source_id,
    customer_orders.order_date,
    LAG(customer_orders.order_date) OVER (
        PARTITION BY customer_orders.customer_key ORDER BY customer_orders.order_date
    ) AS previous_order_date,
    customer_orders.order_date - LAG(customer_orders.order_date) OVER (
        PARTITION BY customer_orders.customer_key ORDER BY customer_orders.order_date
    ) AS days_since_previous_order
FROM customer_orders
JOIN warehouse.dim_customer dc ON dc.customer_key = customer_orders.customer_key
ORDER BY dc.customer_source_id, customer_orders.order_date;
