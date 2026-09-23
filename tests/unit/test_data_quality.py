import pandas as pd
from src.data_quality.checks import (
    DatasetSpec,
    check_duplicate_ids,
    check_impossible_dates,
    check_negative_values,
    check_required_nulls,
    detect_outliers_iqr,
    detect_outliers_zscore,
    run_all_checks,
)
from src.data_quality.profiler import profile_dataframe
from src.data_quality.report import FAIL, PASS, WARN, build_quality_report, save_report


def _orders_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o3"],
            "customer_id": ["c1", "c2", None, "c4"],
            "order_purchase_timestamp": pd.to_datetime(
                ["2018-01-01", "2018-01-02", "2018-01-03", "2018-01-03"]
            ),
            "order_delivered_customer_date": pd.to_datetime(
                ["2018-01-05", "2017-12-30", "2018-01-10", "2018-01-10"]
            ),
            "quantity": [1, -2, 3, 3],
            "price": [10.0, 20.0, 30.0, 1000.0],
        }
    )


def _spec() -> DatasetSpec:
    return DatasetSpec(
        name="orders",
        required_fields=["order_id", "customer_id"],
        id_columns=["order_id"],
        non_negative_columns=["quantity", "price"],
        date_order_pairs=[("order_purchase_timestamp", "order_delivered_customer_date")],
        outlier_columns=["price"],
    )


def test_profile_dataframe_reports_shape_and_missingness():
    profile = profile_dataframe(_orders_df(), "orders")
    assert profile.n_rows == 4
    assert profile.n_cols == 6
    assert profile.missing_count["customer_id"] == 1
    assert profile.missing_pct["customer_id"] == 25.0
    # rows 3 and 4 share order_id but differ on customer_id, so they are not
    # full-row duplicates (that's what check_duplicate_ids tests separately)
    assert profile.n_duplicate_rows == 0


def test_profile_numeric_summary_matches_pandas_describe():
    profile = profile_dataframe(_orders_df(), "orders")
    price_summary = profile.numeric_summary["price"]
    assert price_summary.min == 10.0
    assert price_summary.max == 1000.0


def test_check_required_nulls_flags_missing_customer_id():
    issues = check_required_nulls(_orders_df(), _spec())
    assert any(i.column == "customer_id" and i.count == 1 for i in issues)


def test_check_required_nulls_flags_missing_column_entirely():
    spec = DatasetSpec(name="orders", required_fields=["does_not_exist"])
    issues = check_required_nulls(_orders_df(), spec)
    assert len(issues) == 1
    assert issues[0].detail == "column missing"


def test_check_negative_values_flags_negative_quantity():
    issues = check_negative_values(_orders_df(), _spec())
    assert any(i.column == "quantity" and i.count == 1 for i in issues)


def test_check_impossible_dates_flags_delivery_before_order():
    issues = check_impossible_dates(_orders_df(), _spec())
    assert len(issues) == 1
    assert issues[0].count == 1  # row 2: delivered 2017-12-30 before purchased 2018-01-02


def test_check_duplicate_ids_flags_repeated_order_id():
    issues = check_duplicate_ids(_orders_df(), _spec())
    assert len(issues) == 1
    assert issues[0].count == 1  # one duplicate row beyond the first occurrence


def test_detect_outliers_iqr_flags_extreme_price():
    issues = detect_outliers_iqr(_orders_df(), _spec())
    assert len(issues) == 1
    assert issues[0].count >= 1


def test_detect_outliers_zscore_handles_zero_std_without_error():
    flat_df = pd.DataFrame({"price": [5.0, 5.0, 5.0]})
    spec = DatasetSpec(name="flat", outlier_columns=["price"])
    assert detect_outliers_zscore(flat_df, spec) == []


def test_run_all_checks_combines_every_check():
    issues = run_all_checks(_orders_df(), _spec())
    check_names = {i.check for i in issues}
    assert {"required_null", "negative_value", "impossible_date", "duplicate_id"} <= check_names


def test_build_quality_report_verdict_fail_on_critical_issue():
    profile = profile_dataframe(_orders_df(), "orders")
    issues = run_all_checks(_orders_df(), _spec())
    report = build_quality_report([profile], {"orders": issues})
    assert report.loc[0, "verdict"] == FAIL
    assert report.loc[0, "critical_issues"] > 0


def test_build_quality_report_verdict_pass_with_no_issues():
    clean_df = pd.DataFrame({"id": ["a", "b"], "value": [1, 2]})
    profile = profile_dataframe(clean_df, "clean")
    report = build_quality_report([profile], {"clean": []})
    assert report.loc[0, "verdict"] == PASS


def test_build_quality_report_verdict_warn_on_outlier_only():
    df = pd.DataFrame({"id": ["a", "b", "c", "d"], "value": [1, 2, 3, 1000]})
    spec = DatasetSpec(name="warn_ds", outlier_columns=["value"])
    profile = profile_dataframe(df, "warn_ds")
    issues = run_all_checks(df, spec)
    report = build_quality_report([profile], {"warn_ds": issues})
    assert report.loc[0, "verdict"] == WARN


def test_save_report_writes_csv_and_markdown(tmp_path):
    profile = profile_dataframe(_orders_df(), "orders")
    report = build_quality_report([profile], {"orders": []})
    csv_path, md_path = save_report(report, tmp_path / "dq")
    assert csv_path.exists()
    assert md_path.exists()
    assert "orders" in md_path.read_text(encoding="utf-8")
