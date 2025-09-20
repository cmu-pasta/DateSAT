"""
Unit tests for period arithmetic in the advanced approach.

Tests cover period arithmetic using days-since-epoch conversion
as implemented in the advanced approach.
"""

import pytest

from datesmt.core import Period
from datesmt.symbolic_advanced import AdvancedDateSolver, PeriodVar, to_days_approximate


class TestAdvancedPeriodArithmetic:
    """Test period arithmetic in advanced approach."""

    def test_period_to_days_approximation(self):
        """Test converting Period to approximate days."""
        period = Period(1, 2, 3)
        days = to_days_approximate(period)
        # 1 year * 365 + 2 months * 30 + 3 days = 365 + 60 + 3 = 428
        expected = 1 * 365 + 2 * 30 + 3
        assert days == expected

    def test_period_to_days_zero(self):
        """Test converting zero period to days."""
        period = Period(0, 0, 0)
        days = to_days_approximate(period)
        assert days == 0

    def test_period_to_days_negative(self):
        """Test converting negative period to days."""
        period = Period(-1, -2, -3)
        days = to_days_approximate(period)
        expected = -1 * 365 + -2 * 30 + -3
        assert days == expected

    def test_period_to_days_large_values(self):
        """Test converting large period to days."""
        period = Period(10, 6, 15)
        days = to_days_approximate(period)
        expected = 10 * 365 + 6 * 30 + 15
        assert days == expected


class TestAdvancedPeriodVarArithmetic:
    """Test PeriodVar arithmetic in advanced approach."""

    def test_period_var_creation(self):
        """Test creating PeriodVar in advanced approach."""
        p = PeriodVar("test_period")
        assert p.name == "test_period"
        assert hasattr(p, 'days_var')

    def test_period_var_equality_with_concrete_period(self):
        """Test PeriodVar equality with concrete Period."""
        p = PeriodVar("p")
        concrete_period = Period(1, 2, 3)

        # This should create a Z3 constraint
        constraint = p == concrete_period
        assert constraint is not None
        from z3 import BoolRef

        assert isinstance(constraint, BoolRef)

    def test_period_var_equality_with_another_period_var(self):
        """Test PeriodVar equality with another PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")

        constraint = p1 == p2
        assert constraint is not None
        from z3 import BoolRef

        assert isinstance(constraint, BoolRef)

    def test_period_var_inequality(self):
        """Test PeriodVar inequality."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")

        constraint = p1 != p2
        assert constraint is not None
        from z3 import BoolRef

        assert isinstance(constraint, BoolRef)

    def test_period_var_conversion_to_concrete(self):
        """Test converting PeriodVar to concrete Period via model."""
        p = PeriodVar("p")
        assert hasattr(p, 'to_concrete_period')
        assert callable(p.to_concrete_period)

    def test_period_var_to_days_approximate(self):
        """Test PeriodVar to_days_approximate method."""
        p = PeriodVar("p")
        assert hasattr(p, 'to_days_approximate')
        assert callable(p.to_days_approximate)


class TestAdvancedSolverPeriodOperations:
    """Test period operations through the advanced solver."""

    def test_solver_creation(self):
        """Test creating advanced solver."""
        solver = AdvancedDateSolver()
        assert solver is not None
        assert hasattr(solver, 'add_period_var')

    def test_solver_add_period_var(self):
        """Test adding period variable to solver."""
        solver = AdvancedDateSolver()
        p = solver.add_period_var("test_period")
        assert p.name == "test_period"
        assert "test_period" in solver.period_vars

    def test_solver_period_constraints(self):
        """Test adding period constraints to solver."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")

        # Add constraint that p1 equals a concrete period
        constraint = p1 == Period(1, 2, 3)
        solver.add_constraint(constraint)

        # Add constraint that p1 equals p2
        constraint2 = p1 == p2
        solver.add_constraint(constraint2)

        # Verify constraints were added
        assert len(solver.constraints) == 2

    def test_period_arithmetic_through_constraints(self):
        """Test period arithmetic through Z3 constraints using days."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")

        # Simulate p1 + p2 = p3 by constraining p3 to be the sum
        # In the advanced approach, this is done through days arithmetic

        # Constraint: p3.days = p1.days + p2.days
        from z3 import Int

        days_sum = p1.days_var + p2.days_var
        solver.add_constraint(p3.days_var == days_sum)

        # Verify constraint was added
        assert len(solver.constraints) == 1

    def test_date_plus_period_through_solver(self):
        """Test Date + Period operations through solver."""
        solver = AdvancedDateSolver()
        date_var = solver.add_date_var("x")
        period_var = solver.add_period_var("p")

        # Add constraint: x + p = some_date
        # This would use the DateVar.__add__ method
        result_date = date_var + period_var
        assert result_date is not None
        assert hasattr(result_date, 'days_var')
