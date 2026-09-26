-- DataCo's 4 native delivery statuses (Title Case). Olist has no equivalent
-- field; etl/transform/master_data.py derives one of these for Olist rows
-- by comparing delivered_date to estimated_delivery_date (documented there
-- as a derived, not native, field).

INSERT INTO reference.ref_delivery_status (status_name, is_on_time) VALUES
    ('Advance Shipping', TRUE),
    ('Shipping On Time', TRUE),
    ('Late Delivery', FALSE),
    ('Shipping Cancelled', NULL)
ON CONFLICT (status_name) DO NOTHING;
