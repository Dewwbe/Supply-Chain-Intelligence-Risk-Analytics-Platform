"""Formal hypothesis-testing helpers for the Phase 4 EDA notebooks.

Every test picks its method from the data, not the other way around:
Shapiro-Wilk for normality and Levene's test for equal variance decide
between the parametric test (t-test / one-way ANOVA) and its
non-parametric counterpart (Mann-Whitney U / Kruskal-Wallis) — "test used
(assumption-dependent)" per the Phase 4 spec, not a test picked in advance.

`HypothesisTestResult` carries H0/H1/test/p-value/effect size/interpretation
together so a notebook cell can display one object instead of scattering
these across prints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
import numpy.typing as npt
from scipy import stats

FloatArray: TypeAlias = npt.NDArray[np.float64]

ALPHA_DEFAULT = 0.05
_SHAPIRO_MAX_N = 5000  # scipy's practical limit; sample down for larger groups


@dataclass
class HypothesisTestResult:
    question: str
    h0: str
    h1: str
    test_used: str
    statistic: float
    p_value: float
    effect_size: float
    effect_size_label: str
    alpha: float
    reject_null: bool
    interpretation: str

    def summary(self) -> str:
        verdict = "reject H0" if self.reject_null else "fail to reject H0"
        return (
            f"Q: {self.question}\n"
            f"H0: {self.h0}\n"
            f"H1: {self.h1}\n"
            f"Test: {self.test_used} | statistic={self.statistic:.4f} | "
            f"p={self.p_value:.4g} | {self.effect_size_label}={self.effect_size:.4f}\n"
            f"Result: {verdict} at alpha={self.alpha} — {self.interpretation}"
        )


def _sample_for_normality(values: FloatArray, rng_seed: int = 42) -> FloatArray:
    if len(values) <= _SHAPIRO_MAX_N:
        return values
    rng = np.random.default_rng(rng_seed)
    return rng.choice(values, size=_SHAPIRO_MAX_N, replace=False)


def _all_normal(*groups: FloatArray, alpha: float) -> bool:
    """True if Shapiro-Wilk fails to reject normality for every group."""
    for g in groups:
        if len(g) < 3:
            return False
        _, p = stats.shapiro(_sample_for_normality(np.asarray(g)))
        if p < alpha:
            return False
    return True


def _equal_variance(*groups: FloatArray, alpha: float) -> bool:
    """True if Levene's test fails to reject equal variance across groups."""
    _, p = stats.levene(*groups)
    return bool(p >= alpha)


def compare_two_groups(
    a: FloatArray,
    b: FloatArray,
    *,
    question: str,
    h0: str,
    h1: str,
    alpha: float = ALPHA_DEFAULT,
) -> HypothesisTestResult:
    """Two-sample comparison: Welch/Student's t-test if both groups look normal, else Mann-Whitney U."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    normal = _all_normal(a, b, alpha=alpha)

    if normal:
        equal_var = _equal_variance(a, b, alpha=alpha)
        statistic, p_value = stats.ttest_ind(a, b, equal_var=equal_var)
        pooled_std = np.sqrt(
            ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2)
        )
        effect_size = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else 0.0
        test_used = "Welch's t-test" if not equal_var else "Student's t-test"
        effect_label = "Cohen's d"
    else:
        statistic, p_value = stats.mannwhitneyu(a, b, alternative="two-sided")
        effect_size = 1 - (2 * statistic) / (len(a) * len(b))  # rank-biserial correlation
        test_used = "Mann-Whitney U"
        effect_label = "rank-biserial r"

    reject_null = bool(p_value < alpha)
    direction = "higher" if a.mean() > b.mean() else "lower"
    interpretation = (
        f"group A's mean/median is {direction} than group B's, "
        f"a {'statistically significant' if reject_null else 'not statistically significant'} "
        f"difference (|{effect_label}|={abs(effect_size):.3f})."
    )
    return HypothesisTestResult(
        question,
        h0,
        h1,
        test_used,
        float(statistic),
        float(p_value),
        float(effect_size),
        effect_label,
        alpha,
        reject_null,
        interpretation,
    )


def compare_multiple_groups(
    groups: dict[str, FloatArray],
    *,
    question: str,
    h0: str,
    h1: str,
    alpha: float = ALPHA_DEFAULT,
) -> HypothesisTestResult:
    """K-sample comparison: one-way ANOVA if all groups look normal with equal variance, else Kruskal-Wallis."""
    values = [np.asarray(v, dtype=float) for v in groups.values()]
    normal = _all_normal(*values, alpha=alpha)
    equal_var = _equal_variance(*values, alpha=alpha) if normal else False

    if normal and equal_var:
        statistic, p_value = stats.f_oneway(*values)
        all_values = np.concatenate(values)
        grand_mean = all_values.mean()
        ss_between = sum(len(v) * (v.mean() - grand_mean) ** 2 for v in values)
        ss_total = ((all_values - grand_mean) ** 2).sum()
        effect_size = ss_between / ss_total if ss_total > 0 else 0.0
        test_used = "One-way ANOVA"
        effect_label = "eta-squared"
    else:
        statistic, p_value = stats.kruskal(*values)
        k, n = len(values), sum(len(v) for v in values)
        effect_size = (statistic - k + 1) / (n - k) if n > k else 0.0  # epsilon-squared
        test_used = "Kruskal-Wallis H"
        effect_label = "epsilon-squared"

    reject_null = bool(p_value < alpha)
    ranked = sorted(groups.items(), key=lambda kv: np.mean(kv[1]), reverse=True)
    interpretation = (
        f"{'a statistically significant' if reject_null else 'no statistically significant'} "
        f"difference across {len(groups)} groups ({effect_label}={effect_size:.3f}); "
        f"highest mean/median: {ranked[0][0]}, lowest: {ranked[-1][0]}."
    )
    return HypothesisTestResult(
        question,
        h0,
        h1,
        test_used,
        float(statistic),
        float(p_value),
        float(effect_size),
        effect_label,
        alpha,
        reject_null,
        interpretation,
    )
