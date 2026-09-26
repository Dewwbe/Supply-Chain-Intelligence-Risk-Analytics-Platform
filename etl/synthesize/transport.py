"""Synthetic dim_transport — carrier-level detail DataCo's plain `Shipping Mode`
column doesn't have. Carrier names are deliberately fictional (not real
logistics companies) since this project's fictional client shouldn't imply
real companies' performance data.
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.rng import hash_choice, hash_to_range

CARRIERS = ["Regional Express Co.", "National Freight Partners"]

# Base AED/km by mode — faster service costs more per km. Fixed, disclosed
# assumption, not observed pricing.
_BASE_COST_PER_KM = {
    "Same Day": 2.50,
    "First Class": 1.80,
    "Second Class": 1.20,
    "Standard Class": 0.80,
}

_MIN_DISTANCE_KM = 8
_MAX_DISTANCE_KM = 120


def _transport_source_id(mode_name: str, carrier: str) -> str:
    mode_slug = mode_name.replace(" ", "_").upper()
    carrier_slug = carrier.split()[0].upper()
    return f"TRANSPORT-{mode_slug}-{carrier_slug}"


def build_dim_transport() -> pd.DataFrame:
    """Build the full dim_transport table: 2 carriers x the 4 DataCo shipping modes."""
    rows = []
    for mode_name, base_cost in _BASE_COST_PER_KM.items():
        for carrier in CARRIERS:
            # small deterministic per-carrier price differentiation (+/-15%)
            variance = hash_to_range(f"carrier_variance:{mode_name}:{carrier}", 0.85, 1.15)
            rows.append(
                {
                    "transport_source_id": _transport_source_id(mode_name, carrier),
                    "mode_name": mode_name,
                    "carrier_name": carrier,
                    "vehicle_type": "Van" if mode_name in ("Same Day", "First Class") else "Truck",
                    "avg_cost_per_km": round(base_cost * variance, 2),
                }
            )
    return pd.DataFrame(rows)


def assign_transport(key: str, mode_name: str) -> str | None:
    """Deterministically pick one of the 2 carriers offering `mode_name`."""
    if mode_name not in _BASE_COST_PER_KM:
        return None
    carrier = hash_choice(f"carrier_pick:{key}", CARRIERS)
    return _transport_source_id(mode_name, carrier)


def estimate_transport_cost(key: str, avg_cost_per_km: float) -> float:
    """Synthetic intra-UAE shipment cost: a plausible distance x the transport's cost/km."""
    distance_km = hash_to_range(f"distance:{key}", _MIN_DISTANCE_KM, _MAX_DISTANCE_KM)
    return round(distance_km * avg_cost_per_km, 2)
