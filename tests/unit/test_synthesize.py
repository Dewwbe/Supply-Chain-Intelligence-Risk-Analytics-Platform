import pandas as pd
from etl.synthesize.inventory import _simulate_one_product
from etl.synthesize.product_cost import assign_unit_cost
from etl.synthesize.rng import hash_to_range, hash_to_unit
from etl.synthesize.stores import ONLINE_STORE_ID, assign_store, build_dim_store
from etl.synthesize.supplier_terms import assign_lead_time_days
from etl.synthesize.transport import CARRIERS, assign_transport, build_dim_transport


def test_hash_to_unit_is_deterministic_and_bounded():
    a = hash_to_unit("some-key")
    b = hash_to_unit("some-key")
    assert a == b
    assert 0 <= a < 1


def test_hash_to_range_respects_bounds():
    for key in ["a", "b", "c", "d"]:
        value = hash_to_range(key, 10, 20)
        assert 10 <= value < 20


def test_assign_unit_cost_is_cheaper_than_price_and_deterministic():
    cost1 = assign_unit_cost("Electronics", 100.0)
    cost2 = assign_unit_cost("Electronics", 100.0)
    assert cost1 == cost2
    assert 0 < cost1 < 100.0


def test_assign_unit_cost_handles_non_positive_price():
    assert assign_unit_cost("Electronics", 0) == 0.0
    assert assign_unit_cost("Electronics", None) == 0.0


def test_assign_lead_time_days_in_range_and_deterministic():
    for supplier in ["DEPT-Fitness", "DEPT-Golf", "DEPT-Outdoors"]:
        days = assign_lead_time_days(supplier)
        assert 3 <= days <= 21
        assert days == assign_lead_time_days(supplier)


def test_build_dim_store_has_online_and_physical_rows():
    stores = build_dim_store()
    assert (stores["store_source_id"] == ONLINE_STORE_ID).any()
    assert (stores["store_type"] == "Physical").any()
    assert stores["store_source_id"].is_unique


def test_assign_store_is_deterministic_and_valid():
    store_ids = set(build_dim_store()["store_source_id"])
    for key in ["olist:o1:1", "dataco:d1:1"]:
        store = assign_store(key, "Dubai")
        assert store in store_ids
        assert store == assign_store(key, "Dubai")


def test_build_dim_transport_covers_every_carrier():
    transport = build_dim_transport()
    assert set(transport["carrier_name"]) == set(CARRIERS)
    assert transport["transport_source_id"].is_unique
    assert (transport["avg_cost_per_km"] > 0).all()


def test_assign_transport_returns_none_for_unknown_mode():
    assert assign_transport("key", "Not A Real Mode") is None


def test_assign_transport_is_deterministic():
    a = assign_transport("shipment-1", "Standard Class")
    b = assign_transport("shipment-1", "Standard Class")
    assert a == b


def test_inventory_simulation_never_goes_negative_and_chains_stock():
    dates = pd.date_range("2018-01-01", periods=30, freq="D")
    daily_sold = pd.Series([5] * 30, index=dates)
    result = _simulate_one_product("p1", daily_sold)

    assert (result["opening_stock"] >= 0).all()
    assert (result["closing_stock"] >= 0).all()
    assert (result["sold_quantity"] <= result["opening_stock"] + result["received_quantity"]).all()
    # closing[t] must become opening[t+1]
    assert (
        result["closing_stock"].iloc[:-1].values == result["opening_stock"].iloc[1:].values
    ).all()


def test_inventory_simulation_eventually_restocks_after_depletion():
    dates = pd.date_range("2018-01-01", periods=60, freq="D")
    daily_sold = pd.Series([20] * 60, index=dates)  # demand high enough to force reorders
    result = _simulate_one_product("p2", daily_sold)
    assert (result["received_quantity"] > 0).any()
