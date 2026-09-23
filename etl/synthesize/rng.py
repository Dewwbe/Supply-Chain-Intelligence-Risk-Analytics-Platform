"""Deterministic "randomness" shared by every synthesis module.

Generalizes the hash-bucketing pattern from
`etl/transform/master_data.assign_emirate`: every synthetic value in this
package is a pure function of some natural key, never `random.random()` —
so re-running the pipeline reproduces the exact same synthetic data.
"""

from __future__ import annotations

import hashlib


def hash_to_unit(key: str) -> float:
    """Hash `key` deterministically to a float in [0, 1)."""
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    return int(digest, 16) / 16 ** len(digest)


def hash_to_range(key: str, low: float, high: float) -> float:
    """Hash `key` deterministically to a float in [low, high)."""
    return low + hash_to_unit(key) * (high - low)


def hash_choice(key: str, choices: list) -> object:
    """Deterministically pick one element of `choices` based on `key`."""
    index = int(hash_to_unit(key) * len(choices))
    return choices[min(index, len(choices) - 1)]
