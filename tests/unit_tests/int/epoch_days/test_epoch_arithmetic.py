"""
Unit tests for epoch date arithmetic in datesmt_int.symbolic_epoch_days.

Tests cover the to_days_since_epoch and from_days_since_epoch functions
with March 1, 2000 as the epoch date.

Reference checks use Python's datetime for independence from production code.
"""

from datetime import date, timedelta

import pytest

from datesmt_int.core import Date
from datesmt_int.symbolic_epoch_days import from_days_since_epoch, to_days_since_epoch

EPOCH = Date(2000, 3, 1)
EPOCH_DT = date(2000, 3, 1)


def _as_dt(d: Date) -> date:
    return date(d.year, d.month, d.day)


def _ref_delta_days(a: Date, b: Date = EPOCH) -> int:
    """Signed day difference a - b using datetime."""
    return (_as_dt(a) - _as_dt(b)).days


def _ref_add_days(start: Date, delta: int) -> Date:
    """start + delta days using datetime as reference."""
    dt = _as_dt(start) + timedelta(days=delta)
    return Date(dt.year, dt.month, dt.day)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEpochDateArithmeticBasic:
    """Targeted example-driven tests for epoch conversion."""

    def test_epoch_date_is_zero(self):
        assert to_days_since_epoch(EPOCH) == 0

    def test_epoch_date_roundtrip(self):
        assert from_days_since_epoch(0) == EPOCH

    @pytest.mark.parametrize(
        "date_obj",
        [
            Date(2000, 1, 1),
            Date(2000, 2, 28),
            Date(2000, 2, 29),  # leap day (2000 divisible by 400)
            Date(1999, 12, 31),
            Date(1999, 3, 1),
        ],
    )
    def test_before_epoch_is_negative(self, date_obj: Date):
        days = to_days_since_epoch(date_obj)
        assert days == _ref_delta_days(date_obj)
        assert days < 0

    @pytest.mark.parametrize(
        "date_obj",
        [
            Date(2000, 3, 2),
            Date(2000, 4, 1),
            Date(2000, 5, 1),
            Date(2001, 3, 1),
            Date(2001, 3, 2),
        ],
    )
    def test_after_epoch_is_positive(self, date_obj: Date):
        days = to_days_since_epoch(date_obj)
        assert days == _ref_delta_days(date_obj)
        assert days > 0

    @pytest.mark.parametrize(
        "date_obj",
        [
            # Month boundaries around the epoch year (2000 is leap)
            Date(2000, 1, 1),
            Date(2000, 1, 31),
            Date(2000, 2, 1),
            Date(2000, 2, 29),
            Date(2000, 3, 1),
            Date(2000, 3, 31),
            Date(2000, 4, 1),
            Date(2000, 4, 30),
        ],
    )
    def test_month_boundaries(self, date_obj: Date):
        expected = _ref_delta_days(date_obj)
        got = to_days_since_epoch(date_obj)
        assert got == expected, f"{date_obj} expected {expected}, got {got}"

    @pytest.mark.parametrize(
        "date_obj",
        [
            # Year boundaries 1999/2000 and 2000/2001
            Date(1999, 12, 31),
            Date(2000, 1, 1),
            Date(2000, 12, 31),
            Date(2001, 1, 1),
        ],
    )
    def test_year_boundaries(self, date_obj: Date):
        assert to_days_since_epoch(date_obj) == _ref_delta_days(date_obj)

    @pytest.mark.parametrize(
        "date_obj",
        [
            # Leap-handling checks (2000 leap, 2001 not)
            Date(2000, 2, 28),
            Date(2000, 2, 29),
            Date(2000, 3, 1),
            Date(2001, 2, 28),
            Date(2001, 3, 1),
        ],
    )
    def test_leap_year_handling(self, date_obj: Date):
        assert to_days_since_epoch(date_obj) == _ref_delta_days(date_obj)

    @pytest.mark.parametrize(
        "days",
        [
            # Negative back-conversions
            -1,
            -2,
            -30,
            -60,
            -61,
            # Non-negative back-conversions
            0,
            1,
            30,
            31,
            365,
        ],
    )
    def test_back_conversions_known_offsets(self, days: int):
        # Expected = epoch + offset, using datetime reference
        expected = _ref_add_days(EPOCH, days)
        got = from_days_since_epoch(days)
        assert got == expected, f"days={days} expected {expected}, got {got}"

    def test_bidirectional_conversion_accuracy(self):
        """date -> days -> date must be identity on a set of samples."""
        test_dates = [
            Date(1999, 1, 1),
            Date(1999, 12, 31),
            Date(2000, 1, 1),
            Date(2000, 2, 29),  # Leap year
            Date(2000, 3, 1),  # Epoch
            Date(2000, 3, 2),
            Date(2000, 12, 31),
            Date(2001, 1, 1),
            Date(2001, 2, 28),  # Non-leap year
            Date(2001, 3, 1),
            Date(2020, 2, 29),  # Leap year
            Date(2023, 6, 15),
            Date(2024, 2, 29),  # Leap year
        ]
        for original in test_dates:
            n = to_days_since_epoch(original)
            back = from_days_since_epoch(n)
            assert back == original, f"{original} -> {n} -> {back}"

    def test_large_year_differences_against_reference(self):
        """Derive expectations from the declared epoch."""
        cases = [Date(1900, 3, 1), Date(2100, 2, 28)]
        for d in cases:
            expected = _ref_delta_days(d)
            got = to_days_since_epoch(d)
            assert (
                got == expected
            ), f"Large-span mismatch: {d} expected {expected}, got {got}"

    def test_local_monotonicity(self):
        """+/- 1 day around anchors should map to immediate neighbors."""
        anchors = [
            Date(1999, 12, 30),
            Date(2000, 2, 27),
            Date(2000, 2, 28),
            Date(2000, 2, 29),
            Date(2000, 3, 1),
            Date(2000, 12, 31),
            Date(2001, 1, 1),
        ]
        for anchor in anchors:
            n = to_days_since_epoch(anchor)
            assert from_days_since_epoch(n + 1) == _ref_add_days(anchor, 1)
            assert from_days_since_epoch(n - 1) == _ref_add_days(anchor, -1)

    def test_epoch_consistency(self):
        """Epoch is stable under repeated conversions."""
        for _ in range(5):
            assert to_days_since_epoch(EPOCH) == 0
            assert from_days_since_epoch(0) == EPOCH

    def test_roundtrip_preservation_components(self):
        """Roundtrip preserves all components."""
        test_dates = [
            Date(1999, 12, 31),
            Date(2000, 1, 1),
            Date(2000, 2, 29),  # Leap day
            Date(2000, 3, 1),  # Epoch
            Date(2000, 12, 31),
            Date(2001, 1, 1),
            Date(2001, 2, 28),
            Date(2020, 2, 29),
            Date(2023, 6, 15),
        ]
        for original in test_dates:
            n = to_days_since_epoch(original)
            back = from_days_since_epoch(n)
            assert back.year == original.year
            assert back.month == original.month
            assert back.day == original.day
            assert back == original
