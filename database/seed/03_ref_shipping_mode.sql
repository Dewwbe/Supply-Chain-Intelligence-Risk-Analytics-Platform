-- DataCo's 4 native shipping modes, standardized to Title Case. Olist has no
-- equivalent field, so fact_shipments (DataCo-only, see etl/README.md) is
-- the only consumer of this table.

INSERT INTO reference.ref_shipping_mode (mode_name, typical_speed_rank) VALUES
    ('Same Day', 1),
    ('First Class', 2),
    ('Second Class', 3),
    ('Standard Class', 4)
ON CONFLICT (mode_name) DO NOTHING;
