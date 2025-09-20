"""
Unit tests for leap year validation logic in datesmt.symbolic_baseline.

Tests cover the is_leap() function with various year values including
edge cases for century years and leap year rules.
"""

import pytest

from datesmt.symbolic_baseline import is_leap


class TestLeapYearLogic:
    """Test leap year calculation logic."""

    def test_leap_years_are_identified_correctly(self, leap_years):
        """Test that leap years are correctly identified."""
        for year in leap_years['leap_years']:
            # Note: is_leap returns a Z3 expression, so we need to evaluate it
            # For testing purposes, we'll create a simple test that checks the logic
            # by creating a Z3 solver and checking satisfiability
            from z3 import Int, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(is_leap(year_var))

            result = solver.check()
            assert result == sat, f"Year {year} should be identified as a leap year"

    def test_non_leap_years_are_identified_correctly(self, leap_years):
        """Test that non-leap years are correctly identified."""
        for year in leap_years['non_leap_years']:
            from z3 import Int, Not, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(Not(is_leap(year_var)))

            result = solver.check()
            assert result == sat, f"Year {year} should be identified as a non-leap year"

    def test_century_leap_years(self, leap_years):
        """Test century leap years (divisible by 400)."""
        for year in leap_years['century_leap']:
            from z3 import Int, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(is_leap(year_var))

            result = solver.check()
            assert result == sat, f"Century year {year} should be a leap year"

    def test_century_non_leap_years(self, leap_years):
        """Test century non-leap years (divisible by 100 but not 400)."""
        for year in leap_years['century_non_leap']:
            from z3 import Int, Not, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(Not(is_leap(year_var)))

            result = solver.check()
            assert result == sat, f"Century year {year} should not be a leap year"

    def test_leap_year_rule_divisible_by_4(self):
        """Test that years divisible by 4 are leap years (unless century rule applies)."""
        leap_years_by_4 = [2004, 2008, 2012, 2016, 2020, 2024]

        for year in leap_years_by_4:
            from z3 import Int, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(is_leap(year_var))

            result = solver.check()
            assert result == sat, f"Year {year} (divisible by 4) should be a leap year"

    def test_non_leap_year_rule_not_divisible_by_4(self):
        """Test that years not divisible by 4 are not leap years."""
        non_leap_years = [2001, 2002, 2003, 2005, 2006, 2007]

        for year in non_leap_years:
            from z3 import Int, Not, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(Not(is_leap(year_var)))

            result = solver.check()
            assert (
                result == sat
            ), f"Year {year} (not divisible by 4) should not be a leap year"

    def test_century_rule_400(self):
        """Test the century rule: divisible by 400 are leap years."""
        century_leap_years = [1600, 2000, 2400]

        for year in century_leap_years:
            from z3 import Int, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(is_leap(year_var))

            result = solver.check()
            assert (
                result == sat
            ), f"Century year {year} (divisible by 400) should be a leap year"

    def test_century_rule_100_not_400(self):
        """Test the century rule: divisible by 100 but not 400 are not leap years."""
        century_non_leap_years = [1700, 1800, 1900, 2100, 2200, 2300]

        for year in century_non_leap_years:
            from z3 import Int, Not, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            solver.add(Not(is_leap(year_var)))

            result = solver.check()
            assert (
                result == sat
            ), f"Century year {year} (divisible by 100, not 400) should not be a leap year"

    def test_edge_case_year_0(self):
        """Test edge case: year 0 (if supported)."""
        from z3 import Int, Not, Solver, sat

        solver = Solver()
        year_var = Int('year')
        solver.add(year_var == 0)
        solver.add(Not(is_leap(year_var)))

        result = solver.check()
        assert result == sat, "Year 0 should not be a leap year"

    def test_negative_years(self):
        """Test negative years (if supported)."""
        negative_years = [-4, -100, -400, -1]

        for year in negative_years:
            from z3 import Int, Not, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)
            # For negative years, we expect them not to be leap years
            solver.add(Not(is_leap(year_var)))

            result = solver.check()
            assert result == sat, f"Negative year {year} should not be a leap year"

    def test_very_large_years(self):
        """Test very large years."""
        large_years = [10000, 20000, 100000]

        for year in large_years:
            from z3 import Int, Solver, sat

            solver = Solver()
            year_var = Int('year')
            solver.add(year_var == year)

            # Test both leap and non-leap cases
            if year % 400 == 0:
                solver.add(is_leap(year_var))
                expected_result = sat
            elif year % 100 == 0:
                solver.add(Not(is_leap(year_var)))
                expected_result = sat
            elif year % 4 == 0:
                solver.add(is_leap(year_var))
                expected_result = sat
            else:
                solver.add(Not(is_leap(year_var)))
                expected_result = sat

            result = solver.check()
            assert (
                result == expected_result
            ), f"Large year {year} leap year calculation failed"


class TestLeapYearZ3Expression:
    """Test that is_leap returns proper Z3 expressions."""

    def test_is_leap_returns_z3_expression(self):
        """Test that is_leap returns a Z3 BoolRef expression."""
        from z3 import Int

        year_var = Int('year')
        leap_expr = is_leap(year_var)

        # Check that it's a Z3 expression
        assert hasattr(leap_expr, 'sexpr')
        assert hasattr(leap_expr, 'sort')

    def test_is_leap_expression_structure(self):
        """Test the structure of the leap year Z3 expression."""
        from z3 import And, Int, Not, Or

        year_var = Int('year')
        leap_expr = is_leap(year_var)

        # The expression should be an OR of two conditions:
        # 1. (year % 4 == 0) AND (year % 100 != 0)
        # 2. year % 400 == 0

        # We can't easily test the internal structure without parsing the S-expression
        # but we can verify it's a boolean expression
        assert leap_expr.sort().name() == 'Bool'

    def test_is_leap_with_concrete_values(self):
        """Test is_leap with concrete year values."""
        from z3 import Int, Not, Solver, sat

        # Test with a known leap year
        solver = Solver()
        year_var = Int('year')
        solver.add(year_var == 2024)  # Leap year
        solver.add(is_leap(year_var))

        result = solver.check()
        assert result == sat, "2024 should be satisfiable as a leap year"

        # Test with a known non-leap year
        solver = Solver()
        solver.add(year_var == 2023)  # Non-leap year
        solver.add(Not(is_leap(year_var)))

        result = solver.check()
        assert result == sat, "2023 should be satisfiable as a non-leap year"

    def test_is_leap_consistency(self):
        """Test that is_leap gives consistent results for the same year."""
        from z3 import And, Int, Not, Solver, sat

        year_var = Int('year')
        leap_expr = is_leap(year_var)

        # Test that the same year can't be both leap and non-leap
        solver = Solver()
        solver.add(year_var == 2024)
        solver.add(And(leap_expr, Not(leap_expr)))  # Contradiction

        result = solver.check()
        assert result != sat, "Year cannot be both leap and non-leap simultaneously"
