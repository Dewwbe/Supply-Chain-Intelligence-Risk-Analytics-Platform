-- Canonical order-status taxonomy that both Olist's 8 statuses and DataCo's
-- 9 statuses map onto (see etl/transform/master_data.py:standardize_order_status
-- for the raw -> canonical alias table).

INSERT INTO reference.ref_order_status (status_name, status_group) VALUES
    ('Created', 'Open'),
    ('Approved', 'Open'),
    ('Pending', 'Open'),
    ('Pending Payment', 'Open'),
    ('Processing', 'Open'),
    ('Payment Review', 'Exception'),
    ('On Hold', 'Exception'),
    ('Fraud Review', 'Exception'),
    ('Unavailable', 'Exception'),
    ('Shipped', 'Fulfilled'),
    ('Delivered', 'Fulfilled'),
    ('Completed', 'Fulfilled'),
    ('Closed', 'Fulfilled'),
    ('Cancelled', 'Cancelled')
ON CONFLICT (status_name) DO NOTHING;
