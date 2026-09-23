"""Synthetic dim_product.unit_cost — modeled, not observed.

Neither Olist nor DataCo reports a wholesale/cost price, only what the
customer paid (see docs/kpi_dictionary.md: "Gross Margin ... unit_cost is
modelled, not observed in Olist"). Assigns each category a deterministic
gross-margin rate in [15%, 45%] and derives cost from the observed price.
"""

from __future__ import annotations

from etl.synthesize.rng import hash_to_range

MIN_MARGIN = 0.15
MAX_MARGIN = 0.45


def assign_margin_rate(category: str) -> float:
    """Deterministic gross-margin rate for a product category."""
    return hash_to_range(f"margin:{category}", MIN_MARGIN, MAX_MARGIN)


def assign_unit_cost(category: str, unit_price: float) -> float:
    """Derive a synthetic unit_cost from the real unit_price and a category margin."""
    if unit_price is None or unit_price <= 0:
        return 0.0
    margin_rate = assign_margin_rate(category)
    return round(unit_price * (1 - margin_rate), 2)
