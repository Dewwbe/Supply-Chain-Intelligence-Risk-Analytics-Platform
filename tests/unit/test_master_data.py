from collections import Counter

import pandas as pd
from etl.transform.master_data import (
    EMIRATE_WEIGHTS,
    assign_emirate,
    derive_delivery_status_from_dates,
    standardize_category_name,
    standardize_delivery_status,
    standardize_emirate_alias,
    standardize_order_status,
    standardize_shipping_mode,
)


def test_assign_emirate_is_deterministic():
    assert assign_emirate("olist:SP") == assign_emirate("olist:SP")
    assert assign_emirate("dataco:Southeast Asia") == assign_emirate("dataco:Southeast Asia")


def test_assign_emirate_uses_alias_when_value_is_a_real_emirate():
    assert assign_emirate("DXB") == "Dubai"
    assert assign_emirate("dubai emirate") == "Dubai"
    assert assign_emirate("Abu Dhabi") == "Abu Dhabi"


def test_assign_emirate_distribution_roughly_matches_weights():
    # Large sample of distinct synthetic keys -> bucket counts should track
    # EMIRATE_WEIGHTS within a generous tolerance (this is a hash, not a
    # precise sampler).
    counts = Counter(assign_emirate(f"olist:state-{i}") for i in range(20_000))
    total = sum(counts.values())
    for emirate, weight in EMIRATE_WEIGHTS.items():
        observed = counts[emirate] / total
        assert abs(observed - weight) < 0.03, f"{emirate}: expected ~{weight}, got {observed}"


def test_standardize_emirate_alias_unknown_returns_none():
    assert standardize_emirate_alias("olist:SP") is None


def test_standardize_order_status_covers_both_sources():
    assert standardize_order_status("delivered") == "Delivered"
    assert standardize_order_status("COMPLETE") == "Completed"
    assert standardize_order_status("SUSPECTED_FRAUD") == "Fraud Review"


def test_standardize_delivery_status_title_cases_dataco_values():
    assert standardize_delivery_status("Shipping canceled") == "Shipping Cancelled"
    assert standardize_delivery_status("Late delivery") == "Late Delivery"


def test_standardize_shipping_mode():
    assert standardize_shipping_mode("standard class") == "Standard Class"


def test_standardize_category_name_normalizes_olist_style_values():
    assert standardize_category_name("bed_bath_table") == "Bed Bath Table"
    assert standardize_category_name("Electronics") == "Electronics"


def test_derive_delivery_status_from_dates_cancelled_wins():
    assert (
        derive_delivery_status_from_dates(
            pd.Timestamp("2018-01-05"), pd.Timestamp("2018-01-01"), True
        )
        == "Shipping Cancelled"
    )


def test_derive_delivery_status_from_dates_late_vs_on_time():
    late = derive_delivery_status_from_dates(
        pd.Timestamp("2018-01-10"), pd.Timestamp("2018-01-05"), False
    )
    on_time = derive_delivery_status_from_dates(
        pd.Timestamp("2018-01-03"), pd.Timestamp("2018-01-05"), False
    )
    assert late == "Late Delivery"
    assert on_time == "Shipping On Time"


def test_derive_delivery_status_from_dates_missing_date_is_none():
    assert derive_delivery_status_from_dates(pd.NaT, pd.Timestamp("2018-01-05"), False) is None
