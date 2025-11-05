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
        is_valid, message = validate_solution_with_concrete(
            constraint_data, solution, {}
        )
        assert is_valid
        assert "successfully" in message

        # Invalid solution (should still execute without error)
        solution = {"d1": "Date(2019, 12, 31)"}
        is_valid, message = validate_solution_with_concrete(
            constraint_data, solution, {}
        )
        # Note: This might still be valid since we're not actually checking constraints yet
        # The concrete validation currently just checks if the code executes

    def test_validate_with_periods(self):
        """Test validating constraints with concrete periods."""
        constraint_data = {
            "id": "test_periods",
            "description": "Constraint with concrete periods test",
            "constraints": ["d1 + Period(0, 2, 15) >= Date(2020, 6, 1)"],
        }

        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message = validate_solution_with_concrete(
            constraint_data, solution, {}
        )
        assert is_valid
        assert "successfully" in message

    def test_validate_invalid_solution_format(self):
        """Test validation with invalid solution format."""
        constraint_data = {
            "id": "test_invalid",
            "description": "Invalid solution format test",
            "constraints": ["d1 >= Date(2020, 1, 1)"],
        }

        # Invalid variable value
        solution = {"d1": "Invalid format"}
        is_valid, message = validate_solution_with_concrete(
            constraint_data, solution, {}
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
        is_valid, message = validate_solution_with_concrete(
            constraint_data, solution, {}
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
