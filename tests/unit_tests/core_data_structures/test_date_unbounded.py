"""
datesat.core.Date is a day of the proleptic Gregorian calendar for any integer year,
handled with integer arithmetic. bounded=True selects the original datetime-based
implementation, restricted to Python's datetime.date range, years 1..9999.
"""

import datetime

import pytest
from dateutil.relativedelta import relativedelta

from datesat.core import (
    Date,
    Period,
    civil_from_days,
    days_from_civil,
    is_leap_year,
)


@pytest.mark.parametrize("ymd", [(10000, 1, 1), (0, 1, 1), (0, 2, 29), (-1, 12, 31),
                                 (-2000, 2, 29), (-4, 2, 29), (123456, 7, 31)])
def test_dates_outside_python_range_are_valid(ymd):
    d = Date(*ymd)
    assert (d.year, d.month, d.day) == ymd
    assert not d.bounded


@pytest.mark.parametrize("ymd", [(0, 2, 30), (-1, 2, 29), (-100, 2, 29), (10000, 4, 31),
                                 (10000, 13, 1), (-5, 0, 1)])
def test_calendar_rules_apply_outside_python_range(ymd):
    with pytest.raises(ValueError, match="Invalid date"):
        Date(*ymd)


def test_leap_year_rule_for_any_year():
    assert is_leap_year(0) and is_leap_year(-4) and is_leap_year(-2000) and is_leap_year(10000)
    assert not is_leap_year(-1) and not is_leap_year(-100) and not is_leap_year(10100)


@pytest.mark.parametrize("ymd", [(10000, 1, 1), (0, 12, 31), (-50, 6, 15)])
def test_bounded_rejects_dates_outside_python_range(ymd):
    with pytest.raises(ValueError, match="Invalid date"):
        Date(*ymd, bounded=True)


def test_bounded_accepts_the_ends_of_python_range():
    assert Date(1, 1, 1, bounded=True).bounded
    assert Date(9999, 12, 31, bounded=True).bounded


def test_to_python_date_raises_outside_python_range():
    assert Date(9999, 12, 31).to_python_date() == datetime.date(9999, 12, 31)
    assert Date(1, 1, 1).to_python_date() == datetime.date(1, 1, 1)
    with pytest.raises(ValueError):
        Date(10000, 1, 1).to_python_date()
    with pytest.raises(ValueError):
        Date(0, 12, 31).to_python_date()


def test_comparisons_outside_python_range():
    assert Date(-1, 12, 31) < Date(0, 1, 1) < Date(1, 1, 1) < Date(9999, 12, 31) < Date(10000, 1, 1)
    assert Date(10000, 1, 1) > Date(9999, 12, 31)
    assert Date(-5, 3, 1) >= Date(-5, 2, 28) and Date(-5, 2, 28) <= Date(-5, 3, 1)
    assert Date(0, 2, 29) == Date(0, 2, 29) and Date(0, 2, 29) != Date(0, 3, 1)


def test_arithmetic_crosses_python_range():
    assert Date(9999, 12, 31) + Period(0, 0, 1) == Date(10000, 1, 1)
    assert Date(1, 1, 1) - Period(0, 0, 1) == Date(0, 12, 31)
    assert Date(1, 1, 1) - Period(1, 0, 0) == Date(0, 1, 1)
    assert Date(0, 2, 29) + Period(1, 0, 0) == Date(1, 2, 28)    # end-of-month clamp
    assert Date(-1, 1, 31) + Period(0, 1, 1) == Date(-1, 3, 1)   # clamp to Feb 28, then +1 day
    assert Date(10000, 1, 31) + Period(0, 1, 0) == Date(10000, 2, 29)


def test_bounded_arithmetic_raises_when_result_leaves_python_range():
    # datetime + relativedelta raise (OverflowError or ValueError) as they always did
    with pytest.raises((ValueError, OverflowError)):
        Date(9999, 12, 31, bounded=True) + Period(0, 0, 1)
    with pytest.raises((ValueError, OverflowError)):
        Date(1, 1, 1, bounded=True) - Period(0, 1, 0)
    # relativedelta also rejects a mid-step (after years/months) outside the range;
    # the integer path computes it
    with pytest.raises((ValueError, OverflowError)):
        Date(9999, 6, 1, bounded=True) + Period(1, 0, -400)
    assert Date(9999, 6, 1) + Period(1, 0, -400) == Date(9999, 4, 28)
    assert (Date(9999, 6, 1, bounded=True) + Period(0, 1, 0)).bounded


def test_bounded_and_unbounded_agree_inside_python_range():
    import random

    rng = random.Random(42)
    for _ in range(2000):
        base = datetime.date.fromordinal(rng.randint(400_000, 3_000_000))
        p = Period(rng.randint(-60, 60), rng.randint(-120, 120), rng.randint(-5000, 5000))
        b = Date.from_python_date(base, bounded=True)
        u = Date.from_python_date(base)
        try:
            rb = b + p
        except (ValueError, OverflowError):
            continue
        ru = u + p
        assert rb == ru and rb.bounded and not ru.bounded
        assert (b < Date(2000, 1, 1, bounded=True)) == (u < Date(2000, 1, 1))


def test_arithmetic_matches_relativedelta_inside_python_range():
    import random

    rng = random.Random(20251105)
    for _ in range(3000):
        base = datetime.date.fromordinal(rng.randint(400_000, 3_000_000))
        p = Period(rng.randint(-60, 60), rng.randint(-120, 120), rng.randint(-5000, 5000))
        got = Date.from_python_date(base) + p
        want = base + relativedelta(years=p.years, months=p.months, days=p.days)
        assert (got.year, got.month, got.day) == (want.year, want.month, want.day), (base, p)


def test_days_from_civil_round_trip_and_agreement_with_datetime():
    epoch = datetime.date(1970, 1, 1)
    for o in range(1, datetime.date.max.toordinal(), 9973):
        d = datetime.date.fromordinal(o)
        n = days_from_civil(d.year, d.month, d.day)
        assert n == (d - epoch).days
        assert civil_from_days(n) == (d.year, d.month, d.day)
    for n in list(range(-900_000, -700_000, 3001)) + list(range(2_900_000, 3_300_000, 3001)):
        y, m, d = civil_from_days(n)
        assert Date(y, m, d)  # calendar-valid
        assert days_from_civil(y, m, d) == n
    assert Date(10000, 1, 1).to_days() == Date(9999, 12, 31).to_days() + 1
    assert Date.from_days(Date(-7, 2, 28).to_days()) == Date(-7, 2, 28)
