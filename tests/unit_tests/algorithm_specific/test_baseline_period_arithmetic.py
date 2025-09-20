"""
Unit tests for period arithmetic in the baseline approach.

Tests cover period arithmetic as implemented through the baseline solver
using year/month/day components.
"""

import pytest

from datesmt.core import Period
from datesmt.symbolic_baseline import DateSolver, PeriodVar


class TestBaselinePeriodArithmetic:
    """Test period arithmetic in baseline approach through solver."""

    def test_period_var_creation(self):
        """Test creating PeriodVar in baseline approach."""
        p = PeriodVar("test_period")
        assert p.name == "test_period"
        assert hasattr(p, 'years_var')
        assert hasattr(p, 'months_var')
        assert hasattr(p, 'days_var')

    def test_period_var_equality_with_concrete_period(self):
        """Test PeriodVar equality with concrete Period."""
        p = PeriodVar("p")
        concrete_period = Period(1, 2, 3)

        # This should create a Z3 constraint, not a Python boolean
        constraint = p == concrete_period
        assert constraint is not None
        # The constraint should be a Z3 BoolRef
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
        # This would normally be done with a Z3 model from solver
        # For testing, we'll just verify the method exists
        assert hasattr(p, 'to_concrete_period')
        assert callable(p.to_concrete_period)


class TestBaselineSolverPeriodOperations:
    """Test period operations through the baseline solver."""

    def test_solver_creation(self):
        """Test creating baseline solver."""
        solver = DateSolver()
        assert solver is not None
        assert hasattr(solver, 'add_period_var')

    def test_solver_add_period_var(self):
        """Test adding period variable to solver."""
        solver = DateSolver()
        p = solver.add_period_var("test_period")
        assert p.name == "test_period"
        assert "test_period" in solver.period_vars

    def test_solver_period_constraints(self):
        """Test adding period constraints to solver."""
        solver = DateSolver()
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
        """Test period arithmetic through Z3 constraints."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")

        # Simulate p1 + p2 = p3 by constraining p3 to be the sum
        # In the baseline approach, this would be done through Z3 constraints
        # on the year, month, day components

        # Constraint: p3.years = p1.years + p2.years
        from z3 import Int

        years_sum = p1.years_var + p2.years_var
        solver.add_constraint(p3.years_var == years_sum)

        # Constraint: p3.months = p1.months + p2.months
        months_sum = p1.months_var + p2.months_var
        solver.add_constraint(p3.months_var == months_sum)

        # Constraint: p3.days = p1.days + p2.days
        days_sum = p1.days_var + p2.days_var
        solver.add_constraint(p3.days_var == days_sum)

        # Verify constraints were added
        assert len(solver.constraints) == 3
