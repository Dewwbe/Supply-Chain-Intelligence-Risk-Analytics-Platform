"""The UAE holiday/seasonal calendar (Phase 5).

Two different kinds of "season" live here, and they're not conflated:

1. **Real, published dates** — Ramadan, Eid al-Fitr, Eid al-Adha, National
   Day. These are actual Gregorian-equivalent dates for the Islamic lunar
   calendar (commonly cited estimates; a moon-sighting-dependent holiday can
   shift by a day, which is why each is a range, not a single date) or a
   fixed civil date (National Day, December 2, 1971). Looking these up is
   citing a calendrical fact, not fabricating data.
2. **Stated definitions** — Summer, Back-to-school, Year-end. These are not
   discovered from the data or from any external source; they're declared,
   disclosed month/day windows (e.g. "Summer = June 1 - September 15") used
   consistently every year. A different, equally defensible definition would
   give different test results — that's exactly why `docs/business_requirements.md`
   §7 says these effects must be *tested*, never assumed to exist or to
   point in any particular direction.

Only real UAE public holidays (Eid al-Fitr, Eid al-Adha, National Day) set
`is_uae_holiday` — Ramadan itself is not a public holiday (work hours
shorten; nothing closes), so it only ever sets `season_label`.

Only the years actually spanned by Olist+DataCo (2015-2018) are covered.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

DateRange = tuple[str, str]

RAMADAN_RANGES: list[DateRange] = [
    ("2015-06-18", "2015-07-16"),
    ("2016-06-06", "2016-07-05"),
    ("2017-05-27", "2017-06-24"),
    ("2018-05-16", "2018-06-14"),
]

EID_AL_FITR_RANGES: list[DateRange] = [
    ("2015-07-17", "2015-07-19"),
    ("2016-07-06", "2016-07-08"),
    ("2017-06-25", "2017-06-27"),
    ("2018-06-15", "2018-06-17"),
]

EID_AL_ADHA_RANGES: list[DateRange] = [
    ("2015-09-23", "2015-09-25"),
    ("2016-09-11", "2016-09-13"),
    ("2017-08-31", "2017-09-02"),
    ("2018-08-21", "2018-08-23"),
]

# UAE Union Day, December 2, 1971 — a fixed civil date, not lunar. The
# 1-3 window covers typical public-holiday observance around it.
NATIONAL_DAY_RANGES: list[DateRange] = [
    (f"{year}-12-01", f"{year}-12-03") for year in range(2015, 2019)
]

# Stated month/day definitions (see module docstring #2) — evaluated
# against (month, day), not tied to specific years.
SUMMER_START, SUMMER_END = (6, 1), (9, 15)
BACK_TO_SCHOOL_START, BACK_TO_SCHOOL_END = (8, 15), (9, 15)
YEAR_END_START, YEAR_END_END = (12, 15), (12, 31)


def _in_ranges(date: pd.Timestamp, ranges: list[DateRange]) -> bool:
    return any(pd.Timestamp(start) <= date <= pd.Timestamp(end) for start, end in ranges)


def _in_month_day_window(date: pd.Timestamp, start: tuple[int, int], end: tuple[int, int]) -> bool:
    return start <= (date.month, date.day) <= end


def is_ramadan(date: pd.Timestamp) -> bool:
    return _in_ranges(date, RAMADAN_RANGES)


def is_eid_al_fitr(date: pd.Timestamp) -> bool:
    return _in_ranges(date, EID_AL_FITR_RANGES)


def is_eid_al_adha(date: pd.Timestamp) -> bool:
    return _in_ranges(date, EID_AL_ADHA_RANGES)


def is_eid(date: pd.Timestamp) -> bool:
    return is_eid_al_fitr(date) or is_eid_al_adha(date)


def is_national_day(date: pd.Timestamp) -> bool:
    return _in_ranges(date, NATIONAL_DAY_RANGES)


def is_summer(date: pd.Timestamp) -> bool:
    return _in_month_day_window(date, SUMMER_START, SUMMER_END)


def is_back_to_school(date: pd.Timestamp) -> bool:
    return _in_month_day_window(date, BACK_TO_SCHOOL_START, BACK_TO_SCHOOL_END)


def is_year_end(date: pd.Timestamp) -> bool:
    return _in_month_day_window(date, YEAR_END_START, YEAR_END_END)


def is_uae_public_holiday(date: pd.Timestamp) -> bool:
    """Real public holidays only — Eid (both) and National Day. Not Ramadan/Summer/etc."""
    return is_eid(date) or is_national_day(date)


# Ordered most-specific-first: a day matching more than one category (e.g.
# National Day falling inside a Summer window) gets the more specific label.
SEASONAL_CATEGORIES: dict[str, Callable[[pd.Timestamp], bool]] = {
    "National Day": is_national_day,
    "Eid": is_eid,
    "Ramadan": is_ramadan,
    "Back-to-school": is_back_to_school,
    "Year-end": is_year_end,
    "Summer": is_summer,
}


def season_label(date: pd.Timestamp) -> str | None:
    """The single most-specific season label for `date`, or None."""
    for label, predicate in SEASONAL_CATEGORIES.items():
        if predicate(date):
            return label
    return None


def label_category(dates: pd.Series, category: str) -> pd.Series:
    """Binary label for one category, e.g. label_category(s, 'Eid') -> 'Eid'/'Non-Eid'."""
    predicate = SEASONAL_CATEGORIES[category]
    return dates.apply(lambda d: category if predicate(pd.Timestamp(d)) else f"Non-{category}")
