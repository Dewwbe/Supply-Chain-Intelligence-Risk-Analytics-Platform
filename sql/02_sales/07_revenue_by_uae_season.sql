-- Business question: how does revenue compare across the UAE seasonal/holiday
-- calendar (Ramadan, Eid, National Day, Summer, Back-to-school, Year-end)
-- versus the rest of the year? (See src/common/uae_calendar.py for how each
-- category is defined — published dates for Ramadan/Eid/National Day,
-- disclosed stated windows for Summer/Back-to-school/Year-end.)

SELECT
    COALESCE(dd.season_label, 'Regular') AS season,
    COUNT(DISTINCT dd.full_date) AS days_in_period,
    SUM(fs.sales_amount) AS revenue_aed,
    ROUND(SUM(fs.sales_amount) / COUNT(DISTINCT dd.full_date), 2) AS avg_revenue_per_day_aed
FROM warehouse.fact_sales fs
JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
GROUP BY COALESCE(dd.season_label, 'Regular')
ORDER BY avg_revenue_per_day_aed DESC;
