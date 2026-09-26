"""Currency standardization: every monetary fact is converted to AED.

Rates mirror database/seed/02_ref_currency.sql exactly — keep the two in
sync if either changes. USD/AED is the real, official peg (exact, not an
approximation). BRL/AED has no peg; the rate below is a single fixed
illustrative value for Olist's 2016-2018 data, not a real historical FX
series — disclosed here and in the seed file, never presented as precise.
"""

from __future__ import annotations

FX_TO_AED: dict[str, float] = {
    "AED": 1.0,
    "USD": 3.6725,  # official AED peg
    "BRL": 0.99,  # fixed illustrative approximation, see module docstring
}


def convert_to_aed(amount: float, currency: str) -> float:
    """Convert `amount` in `currency` to AED using the fixed rate table.

    Raises:
        ValueError: if `currency` isn't in FX_TO_AED — a new source currency
            must be added there (and to the seed file) deliberately, not
            silently defaulted to 1:1.
    """
    try:
        rate = FX_TO_AED[currency]
    except KeyError as exc:
        raise ValueError(f"No FX rate configured for currency {currency!r}") from exc
    return amount * rate
