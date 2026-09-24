import numpy as np
import pytest
from src.eda.stats_tests import compare_multiple_groups, compare_two_groups


@pytest.fixture(autouse=True)
def _seed():
    np.random.seed(0)


def test_compare_two_groups_normal_data_uses_t_test():
    a = np.random.normal(loc=100, scale=10, size=200)
    b = np.random.normal(loc=100, scale=10, size=200)
    result = compare_two_groups(a, b, question="q", h0="no diff", h1="diff")
    # Not asserting reject_null here: with identical distributions, ~5% of
    # seeds will (correctly) land p < 0.05 — that's what alpha=0.05 means,
    # not a bug. The real-shift and real-difference tests below cover
    # correct detection; this one only checks the method selection.
    assert "t-test" in result.test_used


def test_compare_two_groups_detects_a_real_shift():
    a = np.random.normal(loc=100, scale=5, size=300)
    b = np.random.normal(loc=130, scale=5, size=300)
    result = compare_two_groups(a, b, question="q", h0="no diff", h1="diff")
    assert result.reject_null is True
    assert result.p_value < 0.05
    assert abs(result.effect_size) > 0.8  # large Cohen's d given a 6-sigma mean shift


def test_compare_two_groups_skewed_data_uses_mann_whitney():
    a = np.random.exponential(scale=2.0, size=300)
    b = np.random.exponential(scale=2.0, size=300)
    result = compare_two_groups(a, b, question="q", h0="no diff", h1="diff")
    assert result.test_used == "Mann-Whitney U"


def test_compare_multiple_groups_normal_equal_variance_uses_anova():
    groups = {
        "A": np.random.normal(100, 10, 150),
        "B": np.random.normal(100, 10, 150),
        "C": np.random.normal(100, 10, 150),
    }
    result = compare_multiple_groups(groups, question="q", h0="no diff", h1="diff")
    assert result.test_used == "One-way ANOVA"
    assert result.reject_null is False


def test_compare_multiple_groups_detects_a_real_difference():
    groups = {
        "Fast": np.random.normal(5, 1, 150),
        "Medium": np.random.normal(10, 1, 150),
        "Slow": np.random.normal(20, 1, 150),
    }
    result = compare_multiple_groups(groups, question="q", h0="no diff", h1="diff")
    assert result.reject_null is True
    assert result.p_value < 0.001
    assert result.effect_size > 0.5


def test_compare_multiple_groups_non_normal_uses_kruskal_wallis():
    groups = {
        "A": np.random.exponential(2.0, 150),
        "B": np.random.exponential(2.0, 150),
        "C": np.random.exponential(2.0, 150),
    }
    result = compare_multiple_groups(groups, question="q", h0="no diff", h1="diff")
    assert result.test_used == "Kruskal-Wallis H"


def test_result_summary_contains_key_fields():
    a = np.random.normal(0, 1, 100)
    b = np.random.normal(0, 1, 100)
    result = compare_two_groups(a, b, question="Does X differ?", h0="H0 text", h1="H1 text")
    summary = result.summary()
    assert "Does X differ?" in summary
    assert "H0 text" in summary
    assert "H1 text" in summary
    assert result.test_used in summary
