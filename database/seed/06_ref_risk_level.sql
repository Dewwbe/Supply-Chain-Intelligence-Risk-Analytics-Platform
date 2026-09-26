-- Supplier risk bands (docs/kpi_dictionary.md §4, used from Phase 7 onward).
-- Seeded now so the reference layer is complete; no fact table FKs to it
-- yet — src/supplier_risk/scoring.py (Phase 7) will.

INSERT INTO reference.ref_risk_level (risk_level, min_score, max_score) VALUES
    ('Low', 0, 24.99),
    ('Medium', 25, 49.99),
    ('High', 50, 74.99),
    ('Critical', 75, 100)
ON CONFLICT (risk_level) DO NOTHING;
