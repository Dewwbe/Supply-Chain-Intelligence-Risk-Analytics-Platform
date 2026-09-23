"""Synthetic dim_supplier.standard_lead_time_days — not present in DataCo/Olist."""

from __future__ import annotations

from etl.synthesize.rng import hash_to_range

MIN_LEAD_DAYS = 3
MAX_LEAD_DAYS = 21


def assign_lead_time_days(supplier_source_id: str) -> int:
    """Deterministic standard lead time (in days) for a supplier."""
    return round(hash_to_range(f"lead_time:{supplier_source_id}", MIN_LEAD_DAYS, MAX_LEAD_DAYS))
