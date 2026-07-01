"""
Unit tests for the bounded Date class in future_work.datesat_bounded.core.

These are copies of the range-bound assertions that used to live in test_date.py
before datesat.core.Date became unbounded. They now target the bounded twin
(future_work.datesat_bounded.core.Date), which reinstates the [1900-03-01,
2100-02-28] range check for solvers under future_work.datesat_bounded.*.
"""

import pytest
from future_work.datesat_bounded.core import Date


def test_bounded_constructor_out_of_range_from_fixture(out_of_range_date_tuple):
    """Formerly-out-of-range calendar-valid dates must raise for the bounded Date."""
    y, m, d = out_of_range_date_tuple
    with pytest.raises(ValueError):
        Date(y, m, d)


def test_bounded_out_of_range_error_message(out_of_range_date_tuple):
    """The bounded Date must surface a range-specific error message."""
    y, m, d = out_of_range_date_tuple
    with pytest.raises(ValueError) as exc_info:
        Date(y, m, d)
    assert "Date outside allowed range" in str(exc_info.value)


def test_bounded_century_leap_year_range_rejects_1600_and_2400():
    """1600-02-29 and 2400-02-29 are calendar-valid leap days but out of the bounded window."""
    for year in [1600, 2400]:
        with pytest.raises(ValueError):
            Date(year, 2, 29)


def test_bounded_min_boundary_accepted():
    """1900-03-01 is the inclusive lower bound - must be accepted."""
    d = Date(1900, 3, 1)
    assert (d.year, d.month, d.day) == (1900, 3, 1)


def test_bounded_max_boundary_accepted():
    """2100-02-28 is the inclusive upper bound - must be accepted."""
    d = Date(2100, 2, 28)
    assert (d.year, d.month, d.day) == (2100, 2, 28)


def test_bounded_just_below_min_rejected():
    """1900-02-28 is one day before the lower bound - must be rejected."""
    with pytest.raises(ValueError) as exc_info:
        Date(1900, 2, 28)
    assert "Date outside allowed range" in str(exc_info.value)


def test_bounded_just_above_max_rejected():
    """2100-03-01 is one day after the upper bound - must be rejected."""
    with pytest.raises(ValueError) as exc_info:
        Date(2100, 3, 1)
    assert "Date outside allowed range" in str(exc_info.value)


def test_bounded_bounded_false_bypasses_range_check():
    """Passing bounded=False should skip the range check but still validate calendar."""
    d = Date(1600, 2, 29, bounded=False)
    assert (d.year, d.month, d.day) == (1600, 2, 29)
    # Calendar validity still applies:
    with pytest.raises(ValueError):
        Date(2023, 2, 29, bounded=False)  # not a leap year


def test_bounded_add_period_out_of_range_raises():
    """Date arithmetic that lands outside the window must raise."""
    with pytest.raises(ValueError) as exc_info:
        Date(1900, 3, 31) - __import__(
            "future_work.datesat_bounded.core", fromlist=["Period"]
        ).Period(0, 1, 0)
    assert "Date outside allowed range" in str(exc_info.value)
