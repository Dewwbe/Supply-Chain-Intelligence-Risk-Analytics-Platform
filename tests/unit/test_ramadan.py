import pandas as pd
from src.eda.ramadan import is_ramadan, label_ramadan


def test_is_ramadan_true_inside_a_known_range():
    assert is_ramadan(pd.Timestamp("2018-06-01")) is True


def test_is_ramadan_false_outside_any_range():
    assert is_ramadan(pd.Timestamp("2018-01-01")) is False


def test_is_ramadan_boundary_dates_are_inclusive():
    assert is_ramadan(pd.Timestamp("2017-05-27")) is True
    assert is_ramadan(pd.Timestamp("2017-06-24")) is True


def test_label_ramadan_vectorized():
    dates = pd.Series(pd.to_datetime(["2018-06-01", "2018-01-01"]))
    labels = label_ramadan(dates)
    assert list(labels) == ["Ramadan", "Non-Ramadan"]
