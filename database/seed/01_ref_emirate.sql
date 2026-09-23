-- The 5 emirates GulfMart operates in (docs/business_requirements.md §1).
-- Weights used for synthetic emirate assignment live in
-- etl/transform/master_data.py, not here — this table is the FK target,
-- not the weighting config.

INSERT INTO reference.ref_emirate (emirate_code, emirate_name, is_gulfmart_operating) VALUES
    ('DXB', 'Dubai', TRUE),
    ('AUH', 'Abu Dhabi', TRUE),
    ('SHJ', 'Sharjah', TRUE),
    ('AJM', 'Ajman', TRUE),
    ('RAK', 'Ras Al Khaimah', TRUE)
ON CONFLICT (emirate_code) DO NOTHING;
