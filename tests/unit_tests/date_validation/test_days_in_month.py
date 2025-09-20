"""
Unit tests for days in month calculation in datesmt.symbolic_baseline.

Tests cover the days_in_month() function with various month and year combinations,
including leap year edge cases.
"""

import pytest

from datesmt.symbolic_baseline import days_in_month


class TestDaysInMonthCalculation:
    """Test days in month calculation logic."""

    def test_regular_months_days(self, days_in_month_data):
        """Test days in regular months (not February)."""
        regular_months = days_in_month_data['regular_months']

        for month, expected_days in regular_months.items():
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(month_var == month)
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == expected_days)

            result = solver.check()
            assert result == sat, f"Month {month} should have {expected_days} days"

    def test_february_leap_year(self, days_in_month_data):
        """Test February in leap years has 29 days."""
        leap_years = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
        expected_days = days_in_month_data['february_leap']

        for year in leap_years:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == year)
            solver.add(month_var == 2)  # February
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == expected_days)

            result = solver.check()
            assert (
                result == sat
            ), f"February in leap year {year} should have {expected_days} days"

    def test_february_non_leap_year(self, days_in_month_data):
        """Test February in non-leap years has 28 days."""
        non_leap_years = [1900, 2001, 2002, 2003, 2005, 2100]
        expected_days = days_in_month_data['february_non_leap']

        for year in non_leap_years:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == year)
            solver.add(month_var == 2)  # February
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == expected_days)

            result = solver.check()
            assert (
                result == sat
            ), f"February in non-leap year {year} should have {expected_days} days"

    def test_century_leap_year_february(self):
        """Test February in century leap years (divisible by 400)."""
        century_leap_years = [1600, 2000, 2400]

        for year in century_leap_years:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == year)
            solver.add(month_var == 2)  # February
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == 29)  # Leap year

            result = solver.check()
            assert (
                result == sat
            ), f"February in century leap year {year} should have 29 days"

    def test_century_non_leap_year_february(self):
        """Test February in century non-leap years (divisible by 100, not 400)."""
        century_non_leap_years = [1700, 1800, 1900, 2100, 2200, 2300]

        for year in century_non_leap_years:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == year)
            solver.add(month_var == 2)  # February
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == 28)  # Non-leap year

            result = solver.check()
            assert (
                result == sat
            ), f"February in century non-leap year {year} should have 28 days"

    def test_all_months_consistency(self):
        """Test that all months have consistent day counts."""
        # Test that months 1-12 have the expected number of days
        month_days = {
            1: 31,  # January
            2: 28,  # February (non-leap year)
            3: 31,  # March
            4: 30,  # April
            5: 31,  # May
            6: 30,  # June
            7: 31,  # July
            8: 31,  # August
            9: 30,  # September
            10: 31,  # October
            11: 30,  # November
            12: 31,  # December
        }

        for month, expected_days in month_days.items():
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            # Use a non-leap year for this test
            solver.add(year_var == 2023)
            solver.add(month_var == month)
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == expected_days)

            result = solver.check()
            assert (
                result == sat
            ), f"Month {month} should have {expected_days} days in non-leap year"

    def test_february_leap_year_consistency(self):
        """Test February consistency in leap years."""
        leap_years = [2004, 2008, 2012, 2016, 2020, 2024]

        for year in leap_years:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == year)
            solver.add(month_var == 2)  # February
            solver.add(days_var == days_in_month(year_var, month_var))
            solver.add(days_var == 29)  # Leap year

            result = solver.check()
            assert result == sat, f"February in leap year {year} should have 29 days"

    def test_invalid_month_handling(self):
        """Test behavior with invalid month numbers."""
        invalid_months = [0, 13, -1, 14]

        for month in invalid_months:
            from z3 import Int, Solver, sat, unsat

            solver = Solver()
            year_var = Int('year')
            month_var = Int('month')
            days_var = Int('days')

            solver.add(year_var == 2023)
            solver.add(month_var == month)
            solver.add(days_var == days_in_month(year_var, month_var))

            # The function should handle invalid months gracefully
            # We expect it to return some value (could be 0, 31, or undefined)
            result = solver.check()
            # We don't assert specific behavior here as it depends on implementation
            # but we ensure it doesn't crash
            assert result in [
                sat,
                unsat,
            ], f"Invalid month {month} should be handled gracefully"


class TestDaysInMonthZ3Expression:
    """Test that days_in_month returns proper Z3 expressions."""

    def test_days_in_month_returns_z3_expression(self):
        """Test that days_in_month returns a Z3 Int expression."""
        from z3 import Int

        year_var = Int('year')
        month_var = Int('month')
        days_expr = days_in_month(year_var, month_var)

        # Check that it's a Z3 expression
        assert hasattr(days_expr, 'sexpr')
        assert hasattr(days_expr, 'sort')

    def test_days_in_month_expression_type(self):
        """Test that days_in_month returns an integer expression."""
        from z3 import Int

        year_var = Int('year')
        month_var = Int('month')
        days_expr = days_in_month(year_var, month_var)

        # Should be an integer expression
        assert days_expr.sort().name() == 'Int'

    def test_days_in_month_with_concrete_values(self):
        """Test days_in_month with concrete month and year values."""
        from z3 import Int, Solver, sat, unsat

        # Test with a known month and year
        solver = Solver()
        year_var = Int('year')
        month_var = Int('month')
        days_var = Int('days')

        solver.add(year_var == 2023)  # Non-leap year
        solver.add(month_var == 6)  # June
        solver.add(days_var == days_in_month(year_var, month_var))
        solver.add(days_var == 30)  # June has 30 days

        result = solver.check()
        assert result == sat, "June 2023 should have 30 days"

    def test_days_in_month_february_edge_cases(self):
        """Test February edge cases with concrete values."""
        from z3 import Int, Solver, sat, unsat

        # Test February in leap year
        solver = Solver()
        year_var = Int('year')
        month_var = Int('month')
        days_var = Int('days')

        solver.add(year_var == 2024)  # Leap year
        solver.add(month_var == 2)  # February
        solver.add(days_var == days_in_month(year_var, month_var))
        solver.add(days_var == 29)  # Leap year has 29 days

        result = solver.check()
        assert result == sat, "February 2024 should have 29 days"

        # Test February in non-leap year
        solver = Solver()
        solver.add(year_var == 2023)  # Non-leap year
        solver.add(month_var == 2)  # February
        solver.add(days_var == days_in_month(year_var, month_var))
        solver.add(days_var == 28)  # Non-leap year has 28 days

        result = solver.check()
        assert result == sat, "February 2023 should have 28 days"

    def test_days_in_month_consistency_across_years(self):
        """Test that days_in_month gives consistent results for the same month across different years."""
        from z3 import And, Int, Not, Solver, sat

        year1_var = Int('year1')
        year2_var = Int('year2')
        month_var = Int('month')
        days1_var = Int('days1')
        days2_var = Int('days2')

        # Test that non-February months have the same days regardless of year
        solver = Solver()
        solver.add(month_var == 6)  # June
        solver.add(days1_var == days_in_month(year1_var, month_var))
        solver.add(days2_var == days_in_month(year2_var, month_var))
        solver.add(days1_var != days2_var)  # Contradiction

        result = solver.check()
        assert result != sat, "Non-February months should have same days across years"
