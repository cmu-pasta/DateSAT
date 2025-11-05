"""
Test concrete validation functionality.
"""

import os
import sys
import pytest

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datesmt.concrete import ConcreteSolver, ConcreteDateVar
from datesmt.core import Date, Period
from validation import (
    parse_date_string,
    parse_period_string,
    validate_solution_with_concrete,
)


class TestConcreteValidation:
    """Test concrete validation functionality."""

    def test_parse_date_string(self):
        """Test parsing date strings."""
        # Valid date
        date = parse_date_string("Date(2020, 3, 15)")
        assert date.year == 2020
        assert date.month == 3
        assert date.day == 15

        # Invalid date format
        with pytest.raises(ValueError):
            parse_date_string("Invalid date")

    def test_parse_period_string(self):
        """Test parsing period strings."""
        # Valid period
        y, m, d = parse_period_string("Period(1, 2, 3)")
        assert y == 1
        assert m == 2
        assert d == 3

        # Invalid period format
        with pytest.raises(ValueError):
            parse_period_string("Invalid period")

    def test_validate_simple_constraint(self):
        """Test validating a simple constraint."""
        constraint_data = {
            "id": "test_simple",
            "description": "Simple constraint test",
            "constraints": ["d1 >= Date(2020, 1, 1)"],
        }

        # Valid solution
        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_simple"
        )
        assert is_valid
        assert "successfully" in message

        # Invalid solution (should be rejected)
        solution = {"d1": "Date(2019, 12, 31)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_simple_invalid"
        )
        assert not is_valid, "Invalid solution should be rejected"
        assert "does not satisfy" in message.lower()

    def test_validate_with_periods(self):
        """Test validating constraints with concrete periods."""
        constraint_data = {
            "id": "test_periods",
            "description": "Constraint with concrete periods test",
            "constraints": ["d1 + Period(0, 2, 15) >= Date(2020, 6, 1)"],
        }

        # Valid solution: Date(2020, 3, 17) + Period(0, 2, 15) = Date(2020, 6, 1) >= Date(2020, 6, 1)
        solution = {"d1": "Date(2020, 3, 17)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_periods"
        )
        assert is_valid, f"Valid solution rejected: {message}"
        assert "successfully" in message

        # Invalid solution: Date(2020, 3, 15) + Period(0, 2, 15) = Date(2020, 5, 30) < Date(2020, 6, 1)
        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_periods_invalid"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"

    def test_validate_invalid_solution_format(self):
        """Test validation with invalid solution format."""
        constraint_data = {
            "id": "test_invalid",
            "description": "Invalid solution format test",
            "constraints": ["d1 >= Date(2020, 1, 1)"],
        }

        # Invalid variable value
        solution = {"d1": "Invalid format"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_invalid"
        )
        assert not is_valid
        assert "Could not parse" in message

    def test_validate_missing_constraint_code(self):
        """Test validation with missing constraint code."""
        constraint_data = {
            "id": "test_empty",
            "description": "Empty constraint test",
            "constraints": [],
        }
        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_empty"
        )
        # Should still execute (empty code is valid)
        assert is_valid

    def test_concrete_solver_basic_operations(self):
        """Test basic operations with concrete solver."""
        solver = ConcreteSolver()

        # Add date variable
        date_var = solver.add_date_var("d1", 2020, 3, 15)
        assert isinstance(date_var, ConcreteDateVar)
        assert date_var.year == 2020
        assert date_var.month == 3
        assert date_var.day == 15

        # Test date arithmetic with core Period
        period = Period(1, 2, 3)
        result = date_var + period
        assert isinstance(result, ConcreteDateVar)
        # The result should be 2020-03-15 + 1 year, 2 months, 3 days = 2021-05-18
        assert result.year == 2021
        assert result.month == 5
        assert result.day == 18

    def test_concrete_date_comparison(self):
        """Test concrete date comparison."""
        solver = ConcreteSolver()
        date1 = solver.add_date_var("d1", 2020, 3, 15)
        date2 = solver.add_date_var("d2", 2020, 3, 16)

        assert date1 < date2
        assert date2 > date1
        assert date1 <= date2
        assert date2 >= date1
        assert date1 != date2

        # Test with Date objects
        date_obj = Date(2020, 3, 15)
        assert date1 == date_obj
        assert date1 >= date_obj
        assert date1 <= date_obj

    def test_leap_year_feb_29_constraint(self):
        """Test the leap year Feb 29 constraint case (the bug we fixed)."""
        constraint_data = {
            "description": "Check if a date is February 29 in a leap year",
            "constraints": [
                "x >= Date(2000, 2, 28)",
                "x <= Date(2000, 3, 1)",
                "x != Date(2000, 2, 28)",
                "x != Date(2000, 3, 1)",
            ],
            "coverage_tags": ["leap_year"],
        }

        # Valid solution: Feb 29, 2000 (leap year)
        solution = {"x": "Date(2000, 2, 29)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_leap_feb29"
        )
        assert is_valid, f"Valid solution rejected: {message}"

        # Invalid solution: Feb 28, 2000 (excluded by constraint)
        solution = {"x": "Date(2000, 2, 28)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_leap_feb28"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"
        assert "does not satisfy" in message.lower()

        # Invalid solution: Mar 1, 2000 (excluded by constraint)
        solution = {"x": "Date(2000, 3, 1)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_leap_mar1"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"

    def test_negative_epoch_constraint(self):
        """Test constraints with negative epoch values (dates before 2000-03-01)."""
        constraint_data = {
            "description": "Range constraint before epoch",
            "constraints": [
                "x >= Date(2000, 2, 27)",
                "x <= Date(2000, 2, 29)",
            ],
            "coverage_tags": [],
        }

        # Valid solution: Feb 28, 2000 (negative epoch: -2)
        solution = {"x": "Date(2000, 2, 28)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_neg_epoch_feb28"
        )
        assert is_valid, f"Valid solution rejected: {message}"

        # Invalid solution: Feb 26, 2000 (too early)
        solution = {"x": "Date(2000, 2, 26)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_neg_epoch_feb26"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"

    def test_invalid_solution_before_epoch(self):
        """Test that invalid solutions before epoch are correctly rejected."""
        constraint_data = {
            "description": "Constraint requiring date after 2023",
            "constraints": [
                "x >= Date(2023, 1, 1)",
            ],
            "coverage_tags": [],
        }

        # Invalid solution: Date(2000, 1, 30) does NOT satisfy x >= Date(2023, 1, 1)
        solution = {"x": "Date(2000, 1, 30)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_invalid_before_epoch"
        )
        assert not is_valid, f"Invalid solution incorrectly accepted: {message}"
        assert "does not satisfy" in message.lower() or "Constraint" in message

        # Valid solution: Date(2023, 6, 15) satisfies x >= Date(2023, 1, 1)
        solution = {"x": "Date(2023, 6, 15)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_valid_after_epoch"
        )
        assert is_valid, f"Valid solution incorrectly rejected: {message}"

    def test_month_vs_days_constraint(self):
        """Test month vs days contrast constraint (the bug case from analysis)."""
        constraint_data = {
            "description": "Month vs days contrast",
            "constraints": [
                "x >= Date(2023, 1, 1)",
                "(x + Period(0, 1, 0)) > (x + Period(0, 0, 31))",
            ],
            "coverage_tags": ["month_vs_days"],
        }

        # The key bug case: Date(2000, 1, 30) was incorrectly validated as satisfying
        # the constraints, but it clearly doesn't satisfy x >= Date(2023, 1, 1)
        # Invalid solution: Date(2000, 1, 30) does NOT satisfy x >= Date(2023, 1, 1)
        solution = {"x": "Date(2000, 1, 30)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_month_vs_days_invalid"
        )
        assert not is_valid, f"Invalid solution incorrectly accepted: {message}"
        assert "does not satisfy" in message.lower() or "Constraint" in message
        
        # Note: The constraint (x + 1 month) > (x + 31 days) is very rarely satisfiable
        # because for most dates, adding 1 month gives approximately the same result
        # as adding 31 days. This constraint set may be UNSAT, but the important thing
        # is that we correctly reject solutions that don't satisfy the first constraint.

    def test_exact_constraint_before_epoch(self):
        """Test exact constraint before epoch boundary."""
        constraint_data = {
            "description": "Exact constraint before epoch",
            "constraints": [
                "x == Date(2000, 2, 28)",
            ],
            "coverage_tags": [],
        }

        # Valid solution: exact match
        solution = {"x": "Date(2000, 2, 28)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_exact_before_epoch"
        )
        assert is_valid, f"Valid solution rejected: {message}"

        # Invalid solution: wrong date
        solution = {"x": "Date(2000, 2, 29)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_exact_before_epoch_invalid"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"

    def test_across_epoch_boundary(self):
        """Test constraint that spans epoch boundary."""
        constraint_data = {
            "description": "Comparison across epoch boundary",
            "constraints": [
                "x >= Date(2000, 2, 29)",
                "x <= Date(2000, 3, 2)",
            ],
            "coverage_tags": [],
        }

        # Valid solution: Mar 1, 2000 (epoch date)
        solution = {"x": "Date(2000, 3, 1)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_across_epoch"
        )
        assert is_valid, f"Valid solution rejected: {message}"

        # Invalid solution: too early
        solution = {"x": "Date(2000, 2, 28)"}
        is_valid, message, _ = validate_solution_with_concrete(
            constraint_data, solution, "test_across_epoch_invalid"
        )
        assert not is_valid, f"Invalid solution accepted: {message}"
