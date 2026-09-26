import pandas as pd
from src.supplier_risk.features import compute_supplier_features, to_risk_inputs


def _shipments():
    return pd.DataFrame(
        {
            "shipment_key": [1, 2, 3, 4],
            "supplier_name": [
                "Fitness Supplier",
                "Fitness Supplier",
                "Golf Supplier",
                "Golf Supplier",
            ],
            "on_time": [True, False, True, True],
            "actual_lead_time_days": [5, 10, 3, 4],
            "quantity": [100, 50, 200, 150],
        }
    )


def _purchase_orders():
    return pd.DataFrame(
        {
            "po_key": [1, 2, 3, 4],
            "supplier_name": [
                "Fitness Supplier",
                "Fitness Supplier",
                "Golf Supplier",
                "Golf Supplier",
            ],
            "order_status": ["Delivered", "Cancelled", "Delivered", "Completed"],
            "unit_cost": [10.0, 12.0, 20.0, 21.0],
        }
    )


def _returns():
    return pd.DataFrame(
        {
            "supplier_name": ["Fitness Supplier", "Golf Supplier"],
            "reason": ["Defective item", "Wrong item shipped"],
            "returned_quantity": [15, 5],
        }
    )


def test_compute_supplier_features_shapes_and_aggregates():
    features = compute_supplier_features(_shipments(), _purchase_orders(), _returns())
    assert set(features["supplier_name"]) == {"Fitness Supplier", "Golf Supplier"}

    fitness = features.set_index("supplier_name").loc["Fitness Supplier"]
    assert fitness["shipment_count"] == 2
    assert fitness["on_time_rate"] == 0.5
    assert fitness["average_lead_time_days"] == 7.5
    assert fitness["cancellation_rate"] == 0.5
    # 15 defective returned out of 150 shipped (100+50)
    assert fitness["defect_rate"] == 0.1


def test_compute_supplier_features_defect_rate_zero_when_no_defective_returns():
    features = compute_supplier_features(_shipments(), _purchase_orders(), _returns())
    golf = features.set_index("supplier_name").loc["Golf Supplier"]
    # Golf's only return reason is "Wrong item shipped", not "Defective item"
    assert golf["defect_rate"] == 0.0


def test_to_risk_inputs_round_trips_columns():
    features = compute_supplier_features(_shipments(), _purchase_orders(), _returns())
    inputs = to_risk_inputs(features)
    assert len(inputs) == 2
    names = {i.supplier_id for i in inputs}
    assert names == {"Fitness Supplier", "Golf Supplier"}
    for risk_input in inputs:
        assert 0 <= risk_input.on_time_rate <= 1
        assert 0 <= risk_input.defect_rate <= 1
