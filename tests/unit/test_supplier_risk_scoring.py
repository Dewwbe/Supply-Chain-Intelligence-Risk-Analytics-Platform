import pytest
from src.supplier_risk.scoring import (
    DEFAULT_WEIGHTS,
    RISK_LEVEL_DEFAULT,
    RISK_LEVEL_THRESHOLDS,
    SupplierRiskInputs,
    _risk_level,
    score_suppliers,
)


def test_default_weights_sum_to_one():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "Low"),
        (24.99, "Low"),
        (25, "Medium"),
        (49.99, "Medium"),
        (50, "High"),
        (74.99, "High"),
        (75, "Critical"),
        (100, "Critical"),
    ],
)
def test_risk_level_boundaries_match_ref_risk_level_seed(score, expected):
    # These exact boundaries must match database/seed/06_ref_risk_level.sql.
    assert _risk_level(score) == expected


def test_risk_level_thresholds_and_default_are_consistent():
    labels = [label for _, label in RISK_LEVEL_THRESHOLDS] + [RISK_LEVEL_DEFAULT]
    assert labels == ["Low", "Medium", "High", "Critical"]


def _supplier(
    supplier_id, on_time_rate, lead_time, lead_time_std, defect_rate, cost_var, cancel_rate
):
    return SupplierRiskInputs(
        supplier_id=supplier_id,
        on_time_rate=on_time_rate,
        average_lead_time_days=lead_time,
        lead_time_std_days=lead_time_std,
        defect_rate=defect_rate,
        cost_variability=cost_var,
        cancellation_rate=cancel_rate,
    )


def test_score_suppliers_ranks_a_clearly_worse_supplier_higher():
    good = _supplier(
        "Good Co",
        on_time_rate=0.98,
        lead_time=3,
        lead_time_std=0.5,
        defect_rate=0.01,
        cost_var=0.05,
        cancel_rate=0.01,
    )
    bad = _supplier(
        "Bad Co",
        on_time_rate=0.40,
        lead_time=20,
        lead_time_std=8,
        defect_rate=0.30,
        cost_var=0.60,
        cancel_rate=0.25,
    )

    result = score_suppliers([good, bad])

    assert list(result["supplier_id"]) == ["Bad Co", "Good Co"]
    assert (
        result.set_index("supplier_id").loc["Bad Co", "risk_score"]
        > result.set_index("supplier_id").loc["Good Co", "risk_score"]
    )
    assert result.set_index("supplier_id").loc["Bad Co", "risk_level"] in {"High", "Critical"}
    assert result.set_index("supplier_id").loc["Good Co", "risk_level"] == "Low"


def test_score_suppliers_output_columns_and_score_range():
    suppliers = [
        _supplier(
            f"S{i}",
            on_time_rate=0.5 + i * 0.05,
            lead_time=5 + i,
            lead_time_std=1 + i * 0.5,
            defect_rate=0.05 * i,
            cost_var=0.1 * i,
            cancel_rate=0.02 * i,
        )
        for i in range(5)
    ]
    result = score_suppliers(suppliers)
    assert list(result.columns) == ["supplier_id", "risk_score", "risk_level"]
    assert (result["risk_score"] >= 0).all()
    assert (result["risk_score"] <= 100).all()


def test_score_suppliers_identical_suppliers_all_score_zero():
    # min-max normalization of identical values -> 0 for every metric -> risk_score 0
    suppliers = [
        _supplier(
            f"S{i}",
            on_time_rate=0.9,
            lead_time=5,
            lead_time_std=1,
            defect_rate=0.05,
            cost_var=0.1,
            cancel_rate=0.02,
        )
        for i in range(3)
    ]
    result = score_suppliers(suppliers)
    assert (result["risk_score"] == 0).all()
    assert (result["risk_level"] == "Low").all()


def test_score_suppliers_respects_custom_weights():
    good = _supplier(
        "A",
        on_time_rate=0.99,
        lead_time=3,
        lead_time_std=0.1,
        defect_rate=0.5,
        cost_var=0.1,
        cancel_rate=0.01,
    )
    bad_on_defect_only = _supplier(
        "B",
        on_time_rate=0.99,
        lead_time=3,
        lead_time_std=0.1,
        defect_rate=0.99,
        cost_var=0.1,
        cancel_rate=0.01,
    )

    all_weight_on_defect = {
        "late_delivery_rate": 0,
        "average_lead_time": 0,
        "lead_time_variability": 0,
        "defect_rate": 1.0,
        "cost_volatility": 0,
        "cancellation_rate": 0,
    }
    result = score_suppliers([good, bad_on_defect_only], weights=all_weight_on_defect)
    assert result.set_index("supplier_id").loc["B", "risk_score"] == pytest.approx(100.0)
    assert result.set_index("supplier_id").loc["A", "risk_score"] == pytest.approx(0.0)
