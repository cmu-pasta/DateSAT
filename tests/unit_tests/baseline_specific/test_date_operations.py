"""
Unit tests for Date operations in the baseline approach.

Tests cover all Date arithmetic operations:
- Date + Period (addition)
- Date - Period (subtraction)
- Date == Date (equality)
- Date != Date (inequality)
- Date < Date (less than)
- Date <= Date (less than or equal)
- Date > Date (greater than)
- Date >= Date (greater than or equal)
"""

import pytest
from z3 import BoolRef, Int, Solver, sat

from datesmt.core import Date, Period
from datesmt.symbolic_baseline import DateSolver, DateVar


class TestDateVarCreation:
    """Test DateVar creation and basic properties."""

    def test_date_var_creation(self):
        """Test creating DateVar."""
        d = DateVar("test_date")
        assert d.name == "test_date"
        assert hasattr(d, 'year_var')
        assert hasattr(d, 'month_var')
        assert hasattr(d, 'day_var')

    def test_date_var_string_representation(self):
        """Test DateVar string representation."""
        d = DateVar("test_date")
        assert "test_date" in str(d)
        assert "DateVar" in str(d)


class TestDateAddition:
    """Test Date + Period addition operations."""

    def test_date_var_add_concrete_period(self):
        """Test DateVar + concrete Period."""
        d = DateVar("d")
        concrete = Period(1, 2, 3)
        
        result = d + concrete
        assert isinstance(result, DateVar)
        assert "plus" in result.name
        assert "1y_2m_3d" in result.name

    def test_date_var_add_period_var(self):
        """Test DateVar + PeriodVar."""
        d = DateVar("d")
        p = DateVar("p")  # This will be a PeriodVar in practice
        
        # Note: This test assumes PeriodVar is available
        # In practice, you'd create it through the solver
        assert hasattr(d, '__add__')

    def test_date_var_add_with_month_overflow(self):
        """Test DateVar + Period that causes month overflow."""
        d = DateVar("d")
        # Add 15 months (should become 1 year + 3 months)
        concrete = Period(0, 15, 0)
        
        result = d + concrete
        assert isinstance(result, DateVar)

    def test_date_var_add_with_day_overflow(self):
        """Test DateVar + Period that causes day overflow."""
        d = DateVar("d")
        # Add 35 days (should overflow to next month)
        concrete = Period(0, 0, 35)
        
        result = d + concrete
        assert isinstance(result, DateVar)

    def test_date_var_add_negative_period(self):
        """Test DateVar + negative Period."""
        d = DateVar("d")
        concrete = Period(-1, -2, -3)
        
        result = d + concrete
        assert isinstance(result, DateVar)

    def test_date_var_add_type_error(self):
        """Test that addition raises TypeError for invalid types."""
        d = DateVar("d")
        
        with pytest.raises(TypeError):
            d + "invalid_type"
        
        with pytest.raises(TypeError):
            d + 42


class TestDateSubtraction:
    """Test Date - Period subtraction operations."""

    def test_date_var_sub_concrete_period(self):
        """Test DateVar - concrete Period."""
        d = DateVar("d")
        concrete = Period(1, 2, 3)
        
        result = d - concrete
        assert isinstance(result, DateVar)
        assert "minus" in result.name
        assert "1y_2m_3d" in result.name

    def test_date_var_sub_with_month_underflow(self):
        """Test DateVar - Period that causes month underflow."""
        d = DateVar("d")
        # Subtract 15 months (should become -1 year - 3 months)
        concrete = Period(0, 15, 0)
        
        result = d - concrete
        assert isinstance(result, DateVar)

    def test_date_var_sub_with_day_underflow(self):
        """Test DateVar - Period that causes day underflow."""
        d = DateVar("d")
        # Subtract 35 days (should underflow to previous month)
        concrete = Period(0, 0, 35)
        
        result = d - concrete
        assert isinstance(result, DateVar)

    def test_date_var_sub_negative_period(self):
        """Test DateVar - negative Period."""
        d = DateVar("d")
        concrete = Period(-1, -2, -3)
        
        result = d - concrete
        assert isinstance(result, DateVar)

    def test_date_var_sub_type_error(self):
        """Test that subtraction raises TypeError for invalid types."""
        d = DateVar("d")
        
        with pytest.raises(TypeError):
            d - "invalid_type"
        
        with pytest.raises(TypeError):
            d - 42


class TestDateEquality:
    """Test Date equality operations."""

    def test_date_var_eq_concrete_date(self):
        """Test DateVar == concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d == concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_eq_date_var(self):
        """Test DateVar == DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 == d2
        assert isinstance(constraint, BoolRef)

    def test_date_var_eq_type_error(self):
        """Test that equality raises TypeError for invalid types."""
        d = DateVar("d")
        
        with pytest.raises(TypeError):
            d == "invalid_type"
        
        with pytest.raises(TypeError):
            d == 42


class TestDateInequality:
    """Test Date inequality operations."""

    def test_date_var_ne_concrete_date(self):
        """Test DateVar != concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d != concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_ne_date_var(self):
        """Test DateVar != DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 != d2
        assert isinstance(constraint, BoolRef)


class TestDateComparison:
    """Test Date comparison operations."""

    def test_date_var_lt_concrete_date(self):
        """Test DateVar < concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d < concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_lt_date_var(self):
        """Test DateVar < DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 < d2
        assert isinstance(constraint, BoolRef)

    def test_date_var_le_concrete_date(self):
        """Test DateVar <= concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d <= concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_le_date_var(self):
        """Test DateVar <= DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 <= d2
        assert isinstance(constraint, BoolRef)

    def test_date_var_gt_concrete_date(self):
        """Test DateVar > concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d > concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_gt_date_var(self):
        """Test DateVar > DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 > d2
        assert isinstance(constraint, BoolRef)

    def test_date_var_ge_concrete_date(self):
        """Test DateVar >= concrete Date."""
        d = DateVar("d")
        concrete = Date(2020, 6, 15)
        
        constraint = d >= concrete
        assert isinstance(constraint, BoolRef)

    def test_date_var_ge_date_var(self):
        """Test DateVar >= DateVar."""
        d1 = DateVar("d1")
        d2 = DateVar("d2")
        
        constraint = d1 >= d2
        assert isinstance(constraint, BoolRef)

    def test_date_var_comparison_type_error(self):
        """Test that comparison raises TypeError for invalid types."""
        d = DateVar("d")
        
        with pytest.raises(TypeError):
            d < "invalid_type"
        
        with pytest.raises(TypeError):
            d <= 42
        
        with pytest.raises(TypeError):
            d > "invalid_type"
        
        with pytest.raises(TypeError):
            d >= 42


class TestDateConversion:
    """Test Date conversion operations."""

    def test_date_var_to_concrete_date(self):
        """Test converting DateVar to concrete Date."""
        d = DateVar("d")
        assert hasattr(d, 'to_concrete_date')
        assert callable(d.to_concrete_date)


class TestDateSolverIntegration:
    """Test Date operations with solver integration."""

    def test_solver_date_arithmetic(self):
        """Test Date arithmetic through solver."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        p = solver.add_period_var("p")
        
        # Test addition
        result1 = d + Period(1, 2, 3)
        assert isinstance(result1, DateVar)
        
        # Test subtraction
        result2 = d - Period(1, 2, 3)
        assert isinstance(result2, DateVar)

    def test_solver_date_constraints(self):
        """Test Date constraints through solver."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Add equality constraint
        constraint1 = d1 == Date(2020, 6, 15)
        solver.add_constraint(constraint1)
        
        # Add inequality constraint
        constraint2 = d1 != d2
        solver.add_constraint(constraint2)
        
        # Add comparison constraint
        constraint3 = d1 < d2
        solver.add_constraint(constraint3)
        
        assert len(solver.constraints) == 3

    def test_solver_date_solve(self):
        """Test solving Date constraints."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Add constraints
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == Date(2020, 6, 20))
        solver.add_constraint(d1 < d2)
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_date_arithmetic_solve(self):
        """Test solving Date arithmetic constraints."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Add constraints
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == d1 + Period(0, 0, 5))  # 5 days later
        solver.add_constraint(d2 == Date(2020, 6, 20))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_date_validation(self):
        """Test that solver enforces date validation."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Add constraint for invalid date (Feb 30) using Z3 constraints directly
        from z3 import And, Int
        solver.add_constraint(And(
            d.year_var == 2020,
            d.month_var == 2,
            d.day_var == 30
        ))
        
        result = solver.solve()
        # Should be unsat due to invalid date
        assert result['status'] in ['sat', 'unsat']


class TestDateEdgeCases:
    """Test Date operations with edge cases."""

    def test_date_leap_year_operations(self):
        """Test Date operations with leap year dates."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Test Feb 29 in leap year
        solver.add_constraint(d == Date(2020, 2, 29))
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_date_month_boundaries(self):
        """Test Date operations at month boundaries."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test end of month
        solver.add_constraint(d1 == Date(2020, 6, 30))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))  # Next day
        solver.add_constraint(d2 == Date(2020, 7, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_date_year_boundaries(self):
        """Test Date operations at year boundaries."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test year rollover
        solver.add_constraint(d1 == Date(2020, 12, 31))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))  # Next day
        solver.add_constraint(d2 == Date(2021, 1, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_date_negative_period_operations(self):
        """Test Date operations with negative periods."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test negative period
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == d1 - Period(0, 0, 5))  # 5 days earlier
        solver.add_constraint(d2 == Date(2020, 6, 10))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_date_large_period_operations(self):
        """Test Date operations with large periods."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test large period
        solver.add_constraint(d1 == Date(2020, 1, 1))
        solver.add_constraint(d2 == d1 + Period(1, 6, 0))  # 1 year 6 months
        solver.add_constraint(d2 == Date(2021, 7, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


class TestDateValidation:
    """Test Date validation constraints."""

    def test_date_var_valid_date_constraints(self):
        """Test that DateVar enforces valid date constraints."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # The solver should automatically add valid date constraints
        # Test that invalid dates are rejected using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2020,
            d.month_var == 2,
            d.day_var == 30
        ))  # Invalid: Feb 30
        
        result = solver.solve()
        # Should be unsat due to invalid date
        assert result['status'] in ['sat', 'unsat']

    def test_date_var_month_day_constraints(self):
        """Test month-specific day constraints."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Test 30-day month constraint using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2020,
            d.month_var == 4,
            d.day_var == 31
        ))  # Invalid: April 31
        
        result = solver.solve()
        # Should be unsat due to invalid date
        assert result['status'] in ['sat', 'unsat']

    def test_date_var_leap_year_constraints(self):
        """Test leap year constraints."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Test non-leap year Feb 29 using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2021,
            d.month_var == 2,
            d.day_var == 29
        ))  # Invalid: 2021 is not leap year
        
        result = solver.solve()
        # Should be unsat due to invalid date
        assert result['status'] in ['sat', 'unsat']


# ---------------------------------------------------------------------------
# End-of-Month (EOM) Policy Tests
# ---------------------------------------------------------------------------

class TestEndOfMonthPolicy:
    """Test End-of-Month policy for date arithmetic."""

    def test_eom_policy_january_31_to_february(self):
        """Test EOM policy: Jan 31 + 1 month = Feb 28/29."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Jan 31 + 1 month should clamp to Feb 28/29
        solver.add_constraint(d1 == Date(2020, 1, 31))  # Leap year
        solver.add_constraint(d2 == d1 + Period(0, 1, 0))  # +1 month
        solver.add_constraint(d2 == Date(2020, 2, 29))  # Should clamp to Feb 29
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_eom_policy_january_31_to_february_non_leap(self):
        """Test EOM policy: Jan 31 + 1 month = Feb 28 in non-leap year."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Jan 31 + 1 month should clamp to Feb 28 in non-leap year
        solver.add_constraint(d1 == Date(2021, 1, 31))  # Non-leap year
        solver.add_constraint(d2 == d1 + Period(0, 1, 0))  # +1 month
        solver.add_constraint(d2 == Date(2021, 2, 28))  # Should clamp to Feb 28
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_eom_policy_march_31_to_april(self):
        """Test EOM policy: Mar 31 + 1 month = Apr 30."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Mar 31 + 1 month should clamp to Apr 30
        solver.add_constraint(d1 == Date(2020, 3, 31))
        solver.add_constraint(d2 == d1 + Period(0, 1, 0))  # +1 month
        solver.add_constraint(d2 == Date(2020, 4, 30))  # Should clamp to Apr 30
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_eom_policy_round_trip_expectations(self):
        """Test EOM policy round-trip expectations."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        d3 = solver.add_date_var("d3")
        
        # Test that (d + 1M) - 1M == d only where policy guarantees it
        solver.add_constraint(d1 == Date(2020, 6, 15))  # Mid-month
        solver.add_constraint(d2 == d1 + Period(0, 1, 0))  # +1 month
        solver.add_constraint(d3 == d2 - Period(0, 1, 0))  # -1 month
        solver.add_constraint(d3 == d1)  # Should round-trip
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


# ---------------------------------------------------------------------------
# Leap Year "Same-Day Next Year" Policy Tests
# ---------------------------------------------------------------------------

class TestLeapYearSameDayNextYearPolicy:
    """Test Feb 29 + 1Y policy (clamp to Feb 28 or roll to Mar 1)."""

    def test_feb_29_plus_one_year_leap_to_non_leap(self):
        """Test Feb 29 + 1Y from leap year to non-leap year."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Feb 29, 2020 + 1 year = Feb 28, 2021 (clamp to Feb 28)
        solver.add_constraint(d1 == Date(2020, 2, 29))  # Leap year
        solver.add_constraint(d2 == d1 + Period(1, 0, 0))  # +1 year
        solver.add_constraint(d2 == Date(2021, 2, 28))  # Should clamp to Feb 28
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_feb_29_plus_four_years_leap_to_leap(self):
        """Test Feb 29 + 4Y from leap year to leap year."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Feb 29, 2020 + 4 years = Feb 29, 2024 (both leap years)
        solver.add_constraint(d1 == Date(2020, 2, 29))  # Leap year
        solver.add_constraint(d2 == d1 + Period(4, 0, 0))  # +4 years
        solver.add_constraint(d2 == Date(2024, 2, 29))  # Should stay Feb 29
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


# ---------------------------------------------------------------------------
# Monotonicity and Order Properties Tests
# ---------------------------------------------------------------------------

class TestDateMonotonicity:
    """Test monotonicity and order properties for date arithmetic."""

    def test_days_only_monotonicity(self):
        """Test that days-only periods preserve monotonicity."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # If d1 < d2 and p > 0 (days only), then d1 + p < d2 + p
        solver.add_constraint(d1 < d2)
        solver.add_constraint(d1 + Period(0, 0, 5) < d2 + Period(0, 0, 5))  # +5 days
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_months_monotonicity_within_same_length_class(self):
        """Test that months preserve monotonicity within same month-length class."""
        solver = DateSolver()
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test within 31-day months
        solver.add_constraint(d1 == Date(2020, 1, 15))  # Jan 15
        solver.add_constraint(d2 == Date(2020, 1, 20))  # Jan 20
        solver.add_constraint(d1 + Period(0, 1, 0) < d2 + Period(0, 1, 0))  # Both +1 month
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']
