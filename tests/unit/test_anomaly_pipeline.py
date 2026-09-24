import numpy as np
import pandas as pd
import src.anomaly_detection.pipeline as pipeline_module
from src.anomaly_detection.pipeline import OUTPUT_COLUMNS, _flagged_rows, detect_domain


def _synthetic_domain_df(entity: str = "Network", n_normal: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    dates = pd.date_range("2020-01-01", periods=n_normal + 1, freq="D")
    values = np.append(rng.normal(50, 5, n_normal), 1000.0)  # obvious outlier at the end
    return pd.DataFrame({"date": dates, "entity": entity, "value": values})


def test_flagged_rows_schema_and_content():
    df = _synthetic_domain_df()
    result = _flagged_rows(df["value"], df["date"], df["entity"], metric="test_metric")

    assert list(result.columns) == OUTPUT_COLUMNS
    assert (result["metric"] == "test_metric").all()
    assert result["anomaly_id"].is_unique
    assert set(result["method"]) <= {"IQR", "Z-Score", "Isolation Forest"}
    # the obvious outlier should be flagged by every method
    assert (result["actual_value"] == 1000.0).sum() == 3


def test_flagged_rows_only_includes_anomalies_not_every_point():
    df = _synthetic_domain_df()
    result = _flagged_rows(df["value"], df["date"], df["entity"], metric="test_metric")
    # 31 input points x 3 methods = 93 possible rows; only the anomalies show up
    assert len(result) < 93


def test_detect_domain_ungrouped(monkeypatch):
    df = _synthetic_domain_df(entity="Network")
    monkeypatch.setitem(pipeline_module.DOMAINS, "fake_metric", (lambda: df, False))
    result = detect_domain("fake_metric")
    assert (result["entity"] == "Network").all()
    assert (result["actual_value"] == 1000.0).any()


def test_detect_domain_grouped_skips_small_groups(monkeypatch):
    big_group = _synthetic_domain_df(entity="BigSupplier", n_normal=30)
    small_group = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "entity": "SmallSupplier",
            "value": [1.0, 2.0, 3.0],
        }
    )
    combined = pd.concat([big_group, small_group], ignore_index=True)

    monkeypatch.setitem(pipeline_module.DOMAINS, "fake_grouped_metric", (lambda: combined, True))
    result = detect_domain("fake_grouped_metric")
    assert "SmallSupplier" not in set(result["entity"])
    assert (result["entity"] == "BigSupplier").all()
