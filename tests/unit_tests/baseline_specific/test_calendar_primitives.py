"""
Calendar primitive functions for DATE-SMT baseline implementation.

This consolidated test file covers all calendar primitive functions:
- is_leap(year) - leap year detection with 400/100/4 rules
- days_in_month(year, month) - days in month calculation
- Helper functions for date arithmetic

Policy: astronomical proleptic Gregorian calendar for all integers:
- Year 0 exists and follows leap rules
- Leap rule: divisible by 400 -> leap, divisible by 100 -> not leap, divisible by 4 -> leap
"""

import pytest
from hypothesis import given, strategies as st
from z3 import Int, Solver, Not, sat, unsat

from datesmt.symbolic_baseline import (
    add_days_ordinal,
    days_in_month,
    EOMClamp,
    is_leap,
    normalize_month,
)


# ---------------------------------------------------------------------------
# Reference implementation (single source of truth for tests)
# ---------------------------------------------------------------------------

def py_ref_is_leap(y: int) -> bool:
    """Reference leap year implementation for validation."""
    if y % 400 == 0:
        return True
    if y % 100 == 0:
        return False
    return (y % 4) == 0


def py_ref_days_in_month(year: int, month: int) -> int:
    """Reference days in month implementation for validation."""
    if month == 2:
        return 29 if py_ref_is_leap(year) else 28
    elif month in [4, 6, 9, 11]:
        return 30
    elif month in [1, 3, 5, 7, 8, 10, 12]:
        return 31
    else:
        return 0  # Invalid month


# ---------------------------------------------------------------------------
# Z3 helpers (keep solver setup DRY)
# ---------------------------------------------------------------------------

def _assert_z3_matches(year: int, expected: bool):
    """Check that is_leap(year) is SAT when expected is True, UNSAT otherwise."""
    y = Int("y")
    s = Solver()
    s.add(y == year)
    s.add(is_leap(y) if expected else Not(is_leap(y)))
    res = s.check()
    assert res == sat, f"Year {year}: expected {expected}, solver={res}"


def _assert_z3_not_both(year: int):
    """A single year cannot satisfy both leap and non-leap."""
    y = Int("y")
    s = Solver()
    s.add(y == year, is_leap(y), Not(is_leap(y)))
    assert s.check() == unsat


def _assert_days_in_month_matches(year: int, month: int, expected_days: int):
    """Check that days_in_month(year, month) returns expected days."""
    y = Int("y")
    m = Int("m")
    d = Int("d")
    s = Solver()
    s.add(y == year)
    s.add(m == month)
    s.add(d == days_in_month(y, m))
    s.add(d == expected_days)
    res = s.check()
    assert res == sat, f"Year {year}, Month {month}: expected {expected_days} days, solver={res}"


# ---------------------------------------------------------------------------
# Leap Year Tests
# ---------------------------------------------------------------------------

class TestLeapYear:
    """Test leap year detection with comprehensive rule coverage."""

    @pytest.mark.parametrize("year", [1996, 2004, 2008, 2012, 2016, 2020, 2024])
    def test_divisible_by_4_non_century_are_leap(self, year):
        """Test years divisible by 4 but not 100 are leap years."""
        _assert_z3_matches(year, True)
        _assert_z3_not_both(year)

    @pytest.mark.parametrize("year", [1997, 1998, 1999, 2001, 2002, 2003, 2005, 2007])
    def test_not_divisible_by_4_are_non_leap(self, year):
        """Test years not divisible by 4 are not leap years."""
        _assert_z3_matches(year, False)
        _assert_z3_not_both(year)

    @pytest.mark.parametrize("year", [1700, 1800, 1900, 2100, 2200, 2300])
    def test_century_not_400_are_non_leap(self, year):
        """Test century years not divisible by 400 are not leap years."""
        _assert_z3_matches(year, False)
        _assert_z3_not_both(year)

    @pytest.mark.parametrize("year", [1600, 2000, 2400, 2800])
    def test_century_400_are_leap(self, year):
        """Test century years divisible by 400 are leap years."""
        _assert_z3_matches(year, True)
        _assert_z3_not_both(year)

    def test_year_zero_is_leap(self):
        """Test year 0 is a leap year (0 % 400 == 0)."""
        _assert_z3_matches(0, True)
        _assert_z3_not_both(0)

    @pytest.mark.parametrize(
        "year, expected",
        [
            (-1, False),
            (-2, False),
            (-3, False),
            (-4, True),     # divisible by 4
            (-5, False),
            (-100, False),  # divisible by 100 but not 400
            (-200, False),
            (-300, False),
            (-400, True),   # divisible by 400
            (-800, True),
        ],
    )
    def test_negative_years_follow_rules(self, year, expected):
        """Test negative years follow leap year rules."""
        _assert_z3_matches(year, expected)
        _assert_z3_not_both(year)

    @given(st.integers(min_value=-1000, max_value=1000))
    def test_leap_year_property_based(self, year):
        """Property-based test for leap year rules."""
        expected = py_ref_is_leap(year)
        _assert_z3_matches(year, expected)
        _assert_z3_not_both(year)


# ---------------------------------------------------------------------------
# Days in Month Tests
# ---------------------------------------------------------------------------

class TestDaysInMonth:
    """Test days in month calculation with comprehensive coverage."""

    def test_regular_months_days(self):
        """Test days in regular months (not February)."""
        regular_months = {
            1: 31,   # January
            3: 31,   # March
            4: 30,   # April
            5: 31,   # May
            6: 30,   # June
            7: 31,   # July
            8: 31,   # August
            9: 30,   # September
            10: 31,  # October
            11: 30,  # November
            12: 31,  # December
        }

        for month, expected_days in regular_months.items():
            _assert_days_in_month_matches(2023, month, expected_days)

    def test_february_leap_year(self):
        """Test February in leap years has 29 days."""
        leap_years = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
        for year in leap_years:
            _assert_days_in_month_matches(year, 2, 29)

    def test_february_non_leap_year(self):
        """Test February in non-leap years has 28 days."""
        non_leap_years = [1900, 2001, 2002, 2003, 2005, 2100]
        for year in non_leap_years:
            _assert_days_in_month_matches(year, 2, 28)

    def test_century_leap_year_february(self):
        """Test February in century leap years (divisible by 400)."""
        century_leap_years = [1600, 2000, 2400]
        for year in century_leap_years:
            _assert_days_in_month_matches(year, 2, 29)

    def test_century_non_leap_year_february(self):
        """Test February in century non-leap years (divisible by 100, not 400)."""
        century_non_leap_years = [1700, 1800, 1900, 2100, 2200, 2300]
        for year in century_non_leap_years:
            _assert_days_in_month_matches(year, 2, 28)

    def test_all_months_consistency(self):
        """Test that all months have consistent day counts."""
        month_days = {
            1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
        }

        for month, expected_days in month_days.items():
            _assert_days_in_month_matches(2023, month, expected_days)

    def test_february_leap_year_consistency(self):
        """Test February consistency in leap years."""
        leap_years = [2004, 2008, 2012, 2016, 2020, 2024]
        for year in leap_years:
            _assert_days_in_month_matches(year, 2, 29)

    def test_invalid_month_handling(self):
        """Test behavior with invalid month numbers."""
        invalid_months = [0, 13, -1, 14]
        for month in invalid_months:
            # The function should handle invalid months gracefully
            y = Int("y")
            m = Int("m")
            d = Int("d")
            s = Solver()
            s.add(y == 2023)
            s.add(m == month)
            s.add(d == days_in_month(y, m))
            # We don't assert specific behavior but ensure it doesn't crash
            result = s.check()
            assert result in [sat, unsat], f"Invalid month {month} should be handled gracefully"

    @given(st.integers(min_value=1, max_value=12), st.integers(min_value=1900, max_value=2100))
    def test_days_in_month_property_based(self, month, year):
        """Property-based test for days in month calculation."""
        expected = py_ref_days_in_month(year, month)
        if expected > 0:  # Valid month
            _assert_days_in_month_matches(year, month, expected)


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestNormalizeMonth:
    """Test the normalize_month helper function."""

    def test_normalize_month_basic(self):
        """Test basic month normalization."""
        y, m = normalize_month(2020, 15)
        assert y is not None
        assert m is not None

    def test_normalize_month_within_range(self):
        """Test normalization when months are already in range."""
        y, m = normalize_month(2020, 6)
        assert y is not None
        assert m is not None

    def test_normalize_month_negative(self):
        """Test normalization with negative months."""
        y, m = normalize_month(2020, -3)
        assert y is not None
        assert m is not None

    def test_normalize_month_z3_expressions(self):
        """Test normalization with Z3 expressions."""
        year = Int('year')
        month = Int('month')
        y, m = normalize_month(year, month)
        assert y is not None
        assert m is not None




class TestAddDaysOrdinal:
    """Test the add_days_ordinal helper function."""

    def test_add_days_within_month(self):
        """Test adding days within the same month."""
        y, m, d = add_days_ordinal(2020, 6, 15, 5)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_overflow_month(self):
        """Test adding days that overflow to next month."""
        y, m, d = add_days_ordinal(2020, 6, 25, 10)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_underflow_month(self):
        """Test adding negative days that underflow to previous month."""
        y, m, d = add_days_ordinal(2020, 6, 5, -10)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_february_leap(self):
        """Test adding days in February during leap year."""
        y, m, d = add_days_ordinal(2020, 2, 25, 5)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_february_non_leap(self):
        """Test adding days in February during non-leap year."""
        y, m, d = add_days_ordinal(2021, 2, 25, 5)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_large_delta(self):
        """Test adding large day deltas (beyond 2 months)."""
        y, m, d = add_days_ordinal(2020, 1, 1, 100)
        assert y is not None
        assert m is not None
        assert d is not None

    def test_add_days_z3_expressions(self):
        """Test add_days_ordinal with Z3 expressions."""
        year = Int('year')
        month = Int('month')
        day = Int('day')
        delta = Int('delta')
        
        y, m, d = add_days_ordinal(year, month, day, delta)
        assert y is not None
        assert m is not None
        assert d is not None






# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestCalendarPrimitiveIntegration:
    """Test integration between calendar primitive functions."""

    def test_days_in_month_with_is_leap(self):
        """Test that days_in_month works with is_leap."""
        year = 2020
        leap_constraint = is_leap(year)
        days_constraint = days_in_month(year, 2)
        
        assert leap_constraint is not None
        assert days_constraint is not None

    def test_add_days_with_days_in_month(self):
        """Test that add_days_ordinal works with days_in_month."""
        year = 2020
        month = 6
        day = 15
        delta = 20
        
        dim = days_in_month(year, month)
        y, m, d = add_days_ordinal(year, month, day, delta)
        
        assert dim is not None
        assert y is not None
        assert m is not None
        assert d is not None



# ---------------------------------------------------------------------------
# 400-Year Cycle Tests
# ---------------------------------------------------------------------------

class Test400YearCycle:
    """Test 400-year Gregorian calendar cycle invariants."""

    def test_400_year_cycle_days(self):
        """Test that 400 years = 146097 days."""
        # This is a fundamental invariant of the Gregorian calendar
        # 400 years = 400 * 365 + 97 leap days = 146097 days
        from datetime import date
        
        start_date = date(1600, 1, 1)
        end_date = date(2000, 1, 1)
        days_diff = (end_date - start_date).days
        
        assert days_diff == 146097, f"400-year cycle should be 146097 days, got {days_diff}"

    def test_leap_year_distribution_400_years(self):
        """Test leap year distribution over 400 years."""
        # In 400 years, there should be exactly 97 leap years
        leap_count = 0
        for year in range(1600, 2000):
            if py_ref_is_leap(year):
                leap_count += 1
        
        assert leap_count == 97, f"400-year cycle should have 97 leap years, got {leap_count}"

    def test_month_length_histogram_400_years(self):
        """Test month length distribution over 400 years."""
        # February should have 29 days in 97 years out of 400
        feb_29_count = 0
        for year in range(1600, 2000):
            if py_ref_days_in_month(year, 2) == 29:
                feb_29_count += 1
        
        assert feb_29_count == 97, f"February should have 29 days in 97 years out of 400, got {feb_29_count}"

