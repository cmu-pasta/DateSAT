"""
Unit tests for the bounded Period class in future_work.datesat_bounded.core.

These are copies of the range-bound assertions that used to live in test_period.py
before datesat.core.Period became unbounded. They now target the bounded twin
(future_work.datesat_bounded.core.Period), which reinstates the MAX_PERIOD_*
range checks for solvers under future_work.datesat_bounded.*.
"""

import pytest
from future_work.datesat_bounded.core import Period


@pytest.mark.parametrize(
    "years,months,days,should_raise",
    [
        # Valid boundary cases
        (200, 0, 0, False),
        (-200, 0, 0, False),
        (0, 2400, 0, False),
        (0, -2400, 0, False),
        (0, 0, 73048, False),
        (0, 0, -73048, False),
        # Invalid cases exceeding bounds
        (201, 0, 0, True),
        (-201, 0, 0, True),
        (0, 2401, 0, True),
        (0, -2401, 0, True),
        (0, 0, 73049, True),
        (0, 0, -73049, True),
        # Mixed valid/invalid
        (200, 0, 73049, True),
        (201, 2400, 0, True),
    ],
)
def test_bounded_period_bounds_validation(years, months, days, should_raise):
    """Bounded Period must reject values outside |years|<=200, |months|<=2400, |days|<=73048."""
    if should_raise:
        with pytest.raises(ValueError) as exc_info:
            Period(years, months, days)
        error_msg = str(exc_info.value)
        if abs(years) > Period.MAX_PERIOD_YEARS:
            assert "years" in error_msg.lower()
            assert str(Period.MAX_PERIOD_YEARS) in error_msg
        if abs(months) > Period.MAX_PERIOD_MONTHS:
            assert "months" in error_msg.lower()
            assert str(Period.MAX_PERIOD_MONTHS) in error_msg
        if abs(days) > Period.MAX_PERIOD_DAYS:
            assert "days" in error_msg.lower()
            assert str(Period.MAX_PERIOD_DAYS) in error_msg
    else:
        p = Period(years, months, days)
        assert (p.years, p.months, p.days) == (years, months, days)


def test_bounded_period_bounds_constants():
    """Constants must be exposed and equal to the historical values."""
    assert Period.MAX_PERIOD_YEARS == 200
    assert Period.MAX_PERIOD_MONTHS == 2400
    assert Period.MAX_PERIOD_DAYS == 73048


def test_bounded_period_arithmetic_respects_bounds():
    """Period arithmetic that would exceed the bounds must raise."""
    # 101 + 101 = 202 > 200 years
    p1 = Period(101, 0, 0)
    p2 = Period(101, 0, 0)
    with pytest.raises(ValueError) as exc_info:
        p1 + p2
    assert "years" in str(exc_info.value).lower()

    # Multiplication that would exceed bounds
    p3 = Period(101, 0, 0)
    with pytest.raises(ValueError) as exc_info:
        p3 * 2
    assert "years" in str(exc_info.value).lower()

    # Days addition that would exceed bounds
    p4 = Period(0, 0, 36525)
    p5 = Period(0, 0, 36525)
    with pytest.raises(ValueError) as exc_info:
        p4 + p5
    assert "days" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "years,months,days",
    [
        (9_999_999, 0, 0),
        (0, 9_999_999, 0),
        (0, 0, 9_999_999),
        (9_999_999, 9_999_999, 9_999_999),
        (-9_999_999, 0, 0),
        (0, -9_999_999, 0),
        (0, 0, -9_999_999),
        (-9_999_999, -9_999_999, -9_999_999),
        (1_000_000, 0, 0),
        (0, 10_000, 0),
        (0, 0, 100_000),
        (500, 5000, 100_000),
    ],
)
def test_bounded_large_period_values_rejected(years, months, days):
    """Very large integer periods must be rejected by the bounded Period."""
    with pytest.raises(ValueError) as exc_info:
        Period(years, months, days)
    error_msg = str(exc_info.value)
    assert "out of range" in error_msg.lower()
    # Period validates components in order: years, months, days
    if abs(years) > Period.MAX_PERIOD_YEARS:
        assert "years" in error_msg.lower()
        assert str(Period.MAX_PERIOD_YEARS) in error_msg
        assert str(years) in error_msg or str(abs(years)) in error_msg
    elif abs(months) > Period.MAX_PERIOD_MONTHS:
        assert "months" in error_msg.lower()
        assert str(Period.MAX_PERIOD_MONTHS) in error_msg
        assert str(months) in error_msg or str(abs(months)) in error_msg
    elif abs(days) > Period.MAX_PERIOD_DAYS:
        assert "days" in error_msg.lower()
        assert str(Period.MAX_PERIOD_DAYS) in error_msg
        assert str(days) in error_msg or str(abs(days)) in error_msg
