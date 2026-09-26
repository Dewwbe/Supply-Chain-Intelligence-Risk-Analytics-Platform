import pandas as pd
from src.common.uae_calendar import (
    SEASONAL_CATEGORIES,
    is_back_to_school,
    is_eid,
    is_national_day,
    is_ramadan,
    is_summer,
    is_uae_public_holiday,
    is_year_end,
    label_category,
    season_label,
)


def test_is_ramadan_true_inside_a_known_range():
    assert is_ramadan(pd.Timestamp("2018-06-01")) is True


def test_is_ramadan_false_outside_any_range():
    assert is_ramadan(pd.Timestamp("2018-01-01")) is False


def test_is_ramadan_boundary_dates_are_inclusive():
    assert is_ramadan(pd.Timestamp("2017-05-27")) is True
    assert is_ramadan(pd.Timestamp("2017-06-24")) is True


def test_is_eid_covers_both_eid_al_fitr_and_eid_al_adha():
    assert is_eid(pd.Timestamp("2018-06-16")) is True  # Eid al-Fitr 2018
    assert is_eid(pd.Timestamp("2018-08-22")) is True  # Eid al-Adha 2018
    assert is_eid(pd.Timestamp("2018-07-01")) is False


def test_is_national_day_every_covered_year():
    for year in range(2015, 2019):
        assert is_national_day(pd.Timestamp(f"{year}-12-02")) is True
    assert is_national_day(pd.Timestamp("2018-12-10")) is False


def test_summer_back_to_school_and_year_end_are_month_day_based_every_year():
    for year in [2015, 2016, 2017, 2018]:
        assert is_summer(pd.Timestamp(f"{year}-07-15")) is True
        assert is_back_to_school(pd.Timestamp(f"{year}-09-01")) is True
        assert is_year_end(pd.Timestamp(f"{year}-12-25")) is True
        assert is_summer(pd.Timestamp(f"{year}-02-01")) is False


def test_is_uae_public_holiday_true_only_for_real_holidays():
    assert is_uae_public_holiday(pd.Timestamp("2018-12-02")) is True  # National Day
    assert is_uae_public_holiday(pd.Timestamp("2018-06-16")) is True  # Eid
    # Ramadan itself is not a public holiday, only Eid at its end is.
    assert is_uae_public_holiday(pd.Timestamp("2018-05-20")) is False


def test_season_label_prioritizes_back_to_school_over_overlapping_summer_window():
    # Back-to-school (Aug 15 - Sep 15) and Summer (Jun 1 - Sep 15) overlap —
    # the more specific label must win.
    label = season_label(pd.Timestamp("2018-09-01"))
    assert label == "Back-to-school"


def test_season_label_none_outside_any_category():
    assert season_label(pd.Timestamp("2018-02-01")) is None


def test_every_seasonal_category_is_reachable():
    # every predicate in the registry must return True for at least one
    # real date, or the category is unreachable/miswired.
    probe_dates = pd.date_range("2015-01-01", "2018-12-31", freq="D")
    for name, predicate in SEASONAL_CATEGORIES.items():
        assert any(predicate(d) for d in probe_dates), f"{name} never matches any date"


def test_label_category_returns_binary_labels():
    dates = pd.Series(pd.to_datetime(["2018-06-16", "2018-01-01"]))
    labels = label_category(dates, "Eid")
    assert list(labels) == ["Eid", "Non-Eid"]
