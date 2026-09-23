"""Master data management: canonicalize inconsistent source values.

Two distinct concerns live here:

1. **Alias canonicalization** — the classic MDM case, "Dubai"/"DUBAI"/"DXB"
   -> "Dubai": a raw value that already denotes a known concept, just
   spelled inconsistently. `standardize_emirate_alias`, `standardize_order_status`,
   `standardize_delivery_status` and `standardize_shipping_mode` all do this,
   via explicit alias tables (never a fuzzy match).
2. **Synthetic assignment** — `assign_emirate` handles the case where the
   source data (Olist=Brazil, DataCo=global) has *no* real UAE value to
   canonicalize at all. It deterministically hashes the raw source location
   into one of GulfMart's 5 emirates using fixed population-like weights.
   This is a relabeling of PUBLIC data for narrative context, disclosed in
   docs/data_dictionary.md — not an observation about real geography.
"""

from __future__ import annotations

import hashlib

import pandas as pd

# --- 1. Alias canonicalization -------------------------------------------------

EMIRATE_ALIASES: dict[str, str] = {
    "dubai": "Dubai",
    "dubai emirate": "Dubai",
    "dxb": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "abudhabi": "Abu Dhabi",
    "auh": "Abu Dhabi",
    "sharjah": "Sharjah",
    "shj": "Sharjah",
    "ajman": "Ajman",
    "ajm": "Ajman",
    "ras al khaimah": "Ras Al Khaimah",
    "ras al-khaimah": "Ras Al Khaimah",
    "rak": "Ras Al Khaimah",
}

ORDER_STATUS_ALIASES: dict[str, str] = {
    # Olist
    "created": "Created",
    "approved": "Approved",
    "processing": "Processing",
    "invoiced": "Processing",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "unavailable": "Unavailable",
    "canceled": "Cancelled",
    # DataCo
    "complete": "Completed",
    "closed": "Closed",
    "pending": "Pending",
    "pending_payment": "Pending Payment",
    "cancelled": "Cancelled",
    "suspected_fraud": "Fraud Review",
    "on_hold": "On Hold",
    "payment_review": "Payment Review",
}

DELIVERY_STATUS_ALIASES: dict[str, str] = {
    "advance shipping": "Advance Shipping",
    "late delivery": "Late Delivery",
    "shipping on time": "Shipping On Time",
    "shipping canceled": "Shipping Cancelled",
    "shipping cancelled": "Shipping Cancelled",
}

SHIPPING_MODE_ALIASES: dict[str, str] = {
    "same day": "Same Day",
    "first class": "First Class",
    "second class": "Second Class",
    "standard class": "Standard Class",
}


def _standardize(raw: str | None, aliases: dict[str, str]) -> str | None:
    """Case/whitespace-insensitive alias lookup; unknown values pass through unchanged."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    key = str(raw).strip().lower()
    return aliases.get(key, str(raw).strip())


def standardize_emirate_alias(raw: str) -> str | None:
    """Canonicalize a value that already denotes a real emirate (e.g. "DXB" -> "Dubai").

    Returns None if `raw` doesn't match any known emirate alias — callers
    (e.g. `assign_emirate`) fall back to synthetic assignment in that case.
    """
    key = str(raw).strip().lower()
    return EMIRATE_ALIASES.get(key)


def standardize_order_status(raw: str) -> str:
    """Canonicalize an Olist or DataCo order status to the shared taxonomy."""
    return _standardize(raw, ORDER_STATUS_ALIASES) or "Unavailable"


def standardize_delivery_status(raw: str) -> str | None:
    """Canonicalize a DataCo delivery status. Olist has no native field — see dates-based derivation below."""
    return _standardize(raw, DELIVERY_STATUS_ALIASES)


def standardize_shipping_mode(raw: str) -> str | None:
    """Canonicalize a DataCo shipping mode."""
    return _standardize(raw, SHIPPING_MODE_ALIASES)


def standardize_category_name(raw: str) -> str:
    """Normalize a product category to Title Case with underscores as spaces.

    Applied to both DataCo's already-English categories and Olist's
    categories after translation (see olist_transform.translate_categories).
    """
    return str(raw).strip().replace("_", " ").title()


def derive_delivery_status_from_dates(
    delivered_at: pd.Timestamp | None,
    estimated_at: pd.Timestamp | None,
    is_cancelled: bool,
) -> str | None:
    """Derive a DataCo-style delivery status for Olist, which has no native field.

    Documented as derived, not observed — unlike DataCo's native column.
    """
    if is_cancelled:
        return "Shipping Cancelled"
    if pd.isna(delivered_at) or pd.isna(estimated_at):
        return None
    return "Late Delivery" if delivered_at > estimated_at else "Shipping On Time"


# --- 2. Synthetic assignment ----------------------------------------------------

EMIRATE_WEIGHTS: dict[str, float] = {
    "Dubai": 0.40,
    "Abu Dhabi": 0.25,
    "Sharjah": 0.20,
    "Ajman": 0.08,
    "Ras Al Khaimah": 0.07,
}


def _weighted_buckets() -> list[tuple[float, str]]:
    """Cumulative (threshold, emirate) pairs in a stable order, for deterministic bucketing."""
    cumulative = 0.0
    buckets = []
    for emirate, weight in EMIRATE_WEIGHTS.items():
        cumulative += weight
        buckets.append((cumulative, emirate))
    return buckets


_BUCKETS = _weighted_buckets()


def assign_emirate(source_location: str) -> str:
    """Deterministically assign one of the 5 emirates to a non-UAE source location.

    Tries alias canonicalization first (in case the value is already a real
    emirate name); otherwise hashes `source_location` into a stable [0, 1)
    value and buckets it by EMIRATE_WEIGHTS. Same input always yields the
    same emirate, and the raw value is preserved separately in
    dim_location.region_source — this function only decides the label.
    """
    alias = standardize_emirate_alias(source_location)
    if alias is not None:
        return alias

    digest = hashlib.sha256(str(source_location).encode("utf-8")).hexdigest()
    fraction = int(digest, 16) / 16 ** len(digest)
    for threshold, emirate in _BUCKETS:
        if fraction < threshold:
            return emirate
    return _BUCKETS[-1][1]
