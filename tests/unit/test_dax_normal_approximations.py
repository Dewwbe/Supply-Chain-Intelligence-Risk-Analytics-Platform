"""Verifies the two normal-distribution approximations used in
powerbi/dax_measures.dax (DAX has no native NORM.S.INV/NORM.S.DIST,
unlike Excel and scipy). Each Python function below is a literal
transcription of its DAX counterpart — same constants, same branches — so
that a passing test here is real evidence the DAX formula is correct, not
just that *some* approximation of a normal distribution works.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm


def acklam_norm_sinv(p: float) -> float:
    """Peter Acklam's inverse standard normal CDF approximation — see the
    `Implied Safety Stock` measure in powerbi/dax_measures.dax.
    """
    p_low = 0.02425
    p_high = 1 - p_low

    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (
            (
                (
                    ((-0.007784894002430293 * q - 0.3223964580411365) * q - 2.400758277161838) * q
                    - 2.549732539343734
                )
                * q
                + 4.374664141464968
            )
            * q
            + 2.938163982698783
        ) / (
            (
                ((0.007784695709041462 * q + 0.3224671290700398) * q + 2.445134137142996) * q
                + 3.754408661907416
            )
            * q
            + 1
        )
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(
            (
                (
                    (
                        ((-0.007784894002430293 * q - 0.3223964580411365) * q - 2.400758277161838)
                        * q
                        - 2.549732539343734
                    )
                    * q
                    + 4.374664141464968
                )
                * q
                + 2.938163982698783
            )
            / (
                (
                    ((0.007784695709041462 * q + 0.3224671290700398) * q + 2.445134137142996) * q
                    + 3.754408661907416
                )
                * q
                + 1
            )
        )
    q = p - 0.5
    r = q * q
    return (
        (
            (
                (
                    ((-39.69683028665376 * r + 220.9460984245205) * r - 275.9285104469687) * r
                    + 138.3577518672690
                )
                * r
                - 30.66479806614716
            )
            * r
            + 2.506628277459239
        )
        * q
        / (
            (
                (
                    ((-54.47609879822406 * r + 161.5858368580409) * r - 155.6989798598866) * r
                    + 66.80131188771972
                )
                * r
                - 13.28068155288572
            )
            * r
            + 1
        )
    )


def zelen_severo_norm_sdist(z: float) -> float:
    """Zelen & Severo (1964) standard normal CDF approximation — see the
    `Scenario Stockout Rate` measure in powerbi/dax_measures.dax.
    """
    abs_z = abs(z)
    t = 1 / (1 + 0.2316419 * abs_z)
    poly = t * (
        0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    pdf = (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z)
    upper_tail = pdf * poly
    return 1 - upper_tail if z >= 0 else upper_tail


@pytest.mark.parametrize(
    "p", [0.0001, 0.001, 0.01, 0.02425, 0.05, 0.25, 0.5, 0.75, 0.95, 0.97575, 0.99, 0.999, 0.9999]
)
def test_acklam_norm_sinv_matches_scipy_ppf(p):
    assert acklam_norm_sinv(p) == pytest.approx(norm.ppf(p), abs=1e-8)


@pytest.mark.parametrize("z", [-6, -3, -1.5, -0.5, 0, 0.5, 1.5, 3, 6])
def test_zelen_severo_norm_sdist_matches_scipy_cdf(z):
    assert zelen_severo_norm_sdist(z) == pytest.approx(norm.cdf(z), abs=1e-7)


def test_acklam_max_error_across_full_clamped_range():
    # engine.py / dax_measures.dax both clamp probabilities to [1e-4, 1-1e-4]
    # before inverting — this is the full range either formula ever sees.
    ps = np.linspace(1e-4, 1 - 1e-4, 5000)
    errors = [abs(acklam_norm_sinv(p) - norm.ppf(p)) for p in ps]
    # Acklam's published bound (~1.15e-9) is for the algorithm plus one
    # Halley's-method refinement step, not included here; measured max
    # error without it is ~3.9e-9 — still negligible next to the scale of
    # avg_daily_demand_units/avg_lead_time_days it's multiplied against.
    assert max(errors) < 5e-9


def test_zelen_severo_max_error_across_plausible_z_range():
    zs = np.linspace(-8, 8, 5000)
    errors = [abs(zelen_severo_norm_sdist(z) - norm.cdf(z)) for z in zs]
    assert max(errors) < 8e-8
