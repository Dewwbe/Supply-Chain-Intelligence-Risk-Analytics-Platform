-- Business question: which categories have the highest return rate?

SELECT
    dp.category,
    SUM(fs.quantity) AS units_sold,
    COALESCE(SUM(fr.returned_quantity), 0) AS units_returned,
    ROUND(
        COALESCE(SUM(fr.returned_quantity), 0)::NUMERIC / NULLIF(SUM(fs.quantity), 0),
        4
    ) AS return_rate
FROM warehouse.fact_sales fs
JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
LEFT JOIN warehouse.fact_returns fr ON fr.sales_key = fs.sales_key
GROUP BY dp.category
ORDER BY return_rate DESC;
