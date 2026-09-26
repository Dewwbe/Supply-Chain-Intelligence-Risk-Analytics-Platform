-- Business question: what percentage of each emirate's revenue does every customer segment contribute?

SELECT
    dl.emirate,
    COALESCE(dc.customer_segment, 'Unclassified') AS customer_segment,
    SUM(fs.sales_amount) AS segment_revenue_aed,
    ROUND(
        100.0 * SUM(fs.sales_amount)
            / SUM(SUM(fs.sales_amount)) OVER (PARTITION BY dl.emirate),
        2
    ) AS pct_of_emirate_revenue
FROM warehouse.fact_sales fs
JOIN warehouse.dim_customer dc ON dc.customer_key = fs.customer_key
JOIN warehouse.dim_location dl ON dl.location_key = fs.location_key
GROUP BY dl.emirate, COALESCE(dc.customer_segment, 'Unclassified')
ORDER BY dl.emirate, pct_of_emirate_revenue DESC;
