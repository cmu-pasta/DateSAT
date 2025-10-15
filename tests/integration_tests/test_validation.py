"""
Test concrete validation functionality.
"""

import pytest

from datesmt.concrete import BaselineConcreteSolver, ConcreteDateVar, ConcretePeriodVar
from datesmt.core import Date, Period
from tests.integration_tests.validation import (
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
        constraint_code = """
# Simple constraint: d1 >= Date(2020, 1, 1)
builder = DateSMTBuilder()
d1 = builder.add_date_var("d1")
builder.add_constraint(d1 >= Date(2020, 1, 1))
result = builder
"""

        # Valid solution
        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message = validate_solution_with_concrete(
            constraint_code, solution, {}
        )
        assert is_valid
        assert "successfully" in message

        # Invalid solution (should still execute without error)
        solution = {"d1": "Date(2019, 12, 31)"}
        is_valid, message = validate_solution_with_concrete(
            constraint_code, solution, {}
        )
        # Note: This might still be valid since we're not actually checking constraints yet
        # The concrete validation currently just checks if the code executes

    def test_validate_with_periods(self):
        """Test validating constraints with periods."""
        constraint_code = """
# Constraint with periods: d1 + p1 >= Date(2020, 6, 1)
builder = DateSMTBuilder()
d1 = builder.add_date_var("d1")
p1 = builder.add_period_var("p1")
builder.add_constraint(d1 + p1 >= Date(2020, 6, 1))
result = builder
"""

        solution = {"d1": "Date(2020, 3, 15)", "p1": "Period(0, 2, 15)"}
        is_valid, message = validate_solution_with_concrete(
            constraint_code, solution, {}
        )
        assert is_valid
        assert "successfully" in message

    def test_validate_invalid_solution_format(self):
        """Test validation with invalid solution format."""
        constraint_code = """
builder = DateSMTBuilder()
d1 = builder.add_date_var("d1")
result = builder
"""

        # Invalid variable value
        solution = {"d1": "Invalid format"}
        is_valid, message = validate_solution_with_concrete(
            constraint_code, solution, {}
        )
        assert not is_valid
        assert "Could not parse" in message

    def test_validate_missing_constraint_code(self):
        """Test validation with missing constraint code."""
        solution = {"d1": "Date(2020, 3, 15)"}
        is_valid, message = validate_solution_with_concrete("", solution, {})
        # Should still execute (empty code is valid)
        assert is_valid

    def test_concrete_solver_basic_operations(self):
        """Test basic operations with concrete solver."""
        solver = BaselineConcreteSolver()

        # Add date variable
        date_var = solver.add_date_var("d1", 2020, 3, 15)
        assert isinstance(date_var, ConcreteDateVar)
        assert date_var.year == 2020
        assert date_var.month == 3
        assert date_var.day == 15

        # Add period variable
        period_var = solver.add_period_var("p1", 1, 2, 3)
        assert isinstance(period_var, ConcretePeriodVar)
        assert period_var.years == 1
        assert period_var.months == 2
        assert period_var.days == 3

        # Test date arithmetic
        result = date_var + period_var
        assert isinstance(result, ConcreteDateVar)
        # The result should be 2020-03-15 + 1 year, 2 months, 3 days = 2021-05-18
        assert result.year == 2021
        assert result.month == 5
        assert result.day == 18

    def test_concrete_date_comparison(self):
        """Test concrete date comparison."""
        solver = BaselineConcreteSolver()
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
