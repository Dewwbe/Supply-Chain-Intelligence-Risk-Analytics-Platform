-- All 7 UAE emirates (Phase 5 "UAE contextual layer"), so this table is a
-- complete geographic reference — but `is_gulfmart_operating` still marks
-- only the 5 GulfMart actually operates in (docs/business_requirements.md
-- §1). Fujairah/Umm Al Quwain exist here for reference completeness only;
-- the synthetic emirate assignment in etl/transform/master_data.py
-- deliberately never assigns sales to them, so dim_location will only ever
-- show the 5 operating emirates in practice — this doesn't change that.
--
-- Weights used for synthetic emirate assignment live in
-- etl/transform/master_data.py, not here — this table is the FK target,
-- not the weighting config.

INSERT INTO reference.ref_emirate (emirate_code, emirate_name, is_gulfmart_operating) VALUES
    ('DXB', 'Dubai', TRUE),
    ('AUH', 'Abu Dhabi', TRUE),
    ('SHJ', 'Sharjah', TRUE),
    ('AJM', 'Ajman', TRUE),
    ('RAK', 'Ras Al Khaimah', TRUE),
    ('FUJ', 'Fujairah', FALSE),
    ('UAQ', 'Umm Al Quwain', FALSE)
ON CONFLICT (emirate_code) DO NOTHING;
