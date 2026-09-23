"""Synthetic dim_store — GulfMart's retail channels.

Olist and DataCo are both pure e-commerce datasets with no store concept at
all. This models GulfMart as a retailer with one online channel plus a
handful of physical stores across the 5 emirates it operates in (see
docs/business_requirements.md §1) — each sales line is assigned a channel
deterministically, weighted toward Online (~75%), consistent with how
`etl/transform/master_data.assign_emirate` relabels geography.
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.rng import hash_choice, hash_to_unit

ONLINE_STORE_ID = "STORE-ONLINE"
ONLINE_SHARE = 0.75

# Physical store count per emirate — a plausible, disclosed footprint, not
# an observed fact about any real retailer.
_PHYSICAL_STORES_PER_EMIRATE = {
    "Dubai": 2,
    "Abu Dhabi": 2,
    "Sharjah": 2,
    "Ajman": 1,
    "Ras Al Khaimah": 1,
}


def _physical_store_id(emirate: str, index: int) -> str:
    slug = emirate.replace(" ", "_").upper()
    return f"STORE-{slug}-{index}"


def build_dim_store() -> pd.DataFrame:
    """Build the full dim_store table: 1 Online store + the physical footprint above."""
    rows = [
        {
            "store_source_id": ONLINE_STORE_ID,
            "store_name": "GulfMart Online",
            "store_type": "Online",
            "emirate": None,
        }
    ]
    for emirate, count in _PHYSICAL_STORES_PER_EMIRATE.items():
        for i in range(1, count + 1):
            rows.append(
                {
                    "store_source_id": _physical_store_id(emirate, i),
                    "store_name": f"GulfMart {emirate} Store {i}",
                    "store_type": "Physical",
                    "emirate": emirate,
                }
            )
    return pd.DataFrame(rows)


def assign_store(key: str, emirate: str) -> str:
    """Deterministically assign a sales line to Online or one of its emirate's physical stores."""
    if hash_to_unit(f"store_channel:{key}") < ONLINE_SHARE:
        return ONLINE_STORE_ID
    count = _PHYSICAL_STORES_PER_EMIRATE.get(emirate, 1)
    choices = [_physical_store_id(emirate, i) for i in range(1, count + 1)]
    return hash_choice(f"store_pick:{key}", choices)
