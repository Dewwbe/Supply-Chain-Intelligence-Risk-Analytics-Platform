-- FX rates to AED. USD is the real, official AED peg (fixed since 1997) —
-- exact, not an approximation. BRL has no peg; the rate here is a single
-- fixed illustrative value (not point-in-time historical), documented in
-- etl/transform/currency.py — do not treat as a real historical FX series.

INSERT INTO reference.ref_currency (currency_code, currency_name, fx_rate_to_aed, rate_is_fixed_peg, notes) VALUES
    ('AED', 'UAE Dirham', 1.000000, TRUE, 'Base currency'),
    ('USD', 'US Dollar', 3.672500, TRUE, 'Official AED peg, exact'),
    ('BRL', 'Brazilian Real', 0.990000, FALSE, 'Fixed illustrative approximation for Olist data (2016-2018), not point-in-time historical FX')
ON CONFLICT (currency_code) DO NOTHING;
