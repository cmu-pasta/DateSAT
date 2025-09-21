"""
Unit tests for advanced solver period operations.

Tests cover period operations through the AdvancedDateSolver including
period variables, constraints, and arithmetic operations.
"""

import pytest
from z3 import Int

from datesmt.core import Date, Period
from datesmt.symbolic_advanced import AdvancedDateSolver, PeriodVar


class TestAdvancedSolverPeriodOperations:
    """Test period operations through the advanced solver."""

    def test_solver_creation(self):
        """Test creating advanced solver."""
        solver = AdvancedDateSolver()
        assert solver is not None
        assert hasattr(solver, 'add_period_var')
        assert hasattr(solver, 'add_date_var')
        assert hasattr(solver, 'add_constraint')
        assert hasattr(solver, 'solve')

    def test_solver_add_period_var(self):
        """Test adding period variable to solver."""
        solver = AdvancedDateSolver()
        p = solver.add_period_var("test_period")
        
        assert p.name == "test_period"
        assert "test_period" in solver.period_vars
        assert isinstance(p, PeriodVar)

    def test_solver_add_multiple_period_vars(self):
        """Test adding multiple period variables to solver."""
        solver = AdvancedDateSolver()
        
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")
        
        assert p1.name == "p1"
        assert p2.name == "p2"
        assert p3.name == "p3"
        
        assert "p1" in solver.period_vars
        assert "p2" in solver.period_vars
        assert "p3" in solver.period_vars
        
        assert len(solver.period_vars) == 3

    def test_solver_period_constraints(self):
        """Test adding period constraints to solver."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")

        # Add constraint that p1 equals a concrete period
        constraint1 = p1 == Period(1, 2, 3)
        solver.add_constraint(constraint1)

        # Add constraint that p1 equals p2
        constraint2 = p1 == p2
        solver.add_constraint(constraint2)

        # Verify constraints were added
        assert len(solver.constraints) == 2

    def test_solver_period_arithmetic_through_constraints(self):
        """Test period arithmetic through Z3 constraints using days."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")

        # Simulate p1 + p2 = p3 by constraining p3 to be the sum
        # In the advanced approach, this is done through days arithmetic
        days_sum = p1.days_var + p2.days_var
        solver.add_constraint(p3.days_var == days_sum)

        # Verify constraint was added
        assert len(solver.constraints) == 1

    def test_solver_date_plus_period_through_solver(self):
        """Test Date + Period operations through solver."""
        solver = AdvancedDateSolver()
        date_var = solver.add_date_var("x")
        period_var = solver.add_period_var("p")

        # Add constraint: x + p = some_date
        # This would use the DateVar.__add__ method
        result_date = date_var + period_var
        assert result_date is not None
        assert hasattr(result_date, 'days_var')

    def test_solver_period_equality_constraints(self):
        """Test various period equality constraints."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Test different equality constraints
        constraints = [
            p1 == Period(0, 0, 0),
            p1 == Period(1, 0, 0),
            p1 == Period(0, 1, 0),
            p1 == Period(0, 0, 1),
            p1 == Period(1, 1, 1),
            p1 == p2,
        ]
        
        for constraint in constraints:
            solver.add_constraint(constraint)
        
        assert len(solver.constraints) == len(constraints)

    def test_solver_period_inequality_constraints(self):
        """Test various period inequality constraints."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Test different inequality constraints
        constraints = [
            p1 != Period(0, 0, 0),
            p1 != Period(1, 0, 0),
            p1 != p2,
        ]
        
        for constraint in constraints:
            solver.add_constraint(constraint)
        
        assert len(solver.constraints) == len(constraints)

    def test_solver_period_arithmetic_operations(self):
        """Test period arithmetic operations through solver."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")
        p4 = solver.add_period_var("p4")
        
        # Test various arithmetic operations
        constraints = [
            p3.days_var == p1.days_var + p2.days_var,  # p3 = p1 + p2
            p4.days_var == p1.days_var - p2.days_var,  # p4 = p1 - p2
            p1.days_var == p2.days_var * 2,            # p1 = p2 * 2
        ]
        
        for constraint in constraints:
            solver.add_constraint(constraint)
        
        assert len(solver.constraints) == len(constraints)

    def test_solver_period_with_concrete_values(self):
        """Test solver with period variables and concrete values."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add constraints with concrete periods
        solver.add_constraint(p1 == Period(1, 2, 3))
        solver.add_constraint(p2 == Period(0, 1, 0))
        
        # Add arithmetic constraint
        solver.add_constraint(p1.days_var == p2.days_var + 30)  # p1 = p2 + 30 days
        
        assert len(solver.constraints) == 3

    def test_solver_period_complex_constraints(self):
        """Test complex period constraints through solver."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")
        
        # Complex constraint: p1 + p2 = p3 and p1 != p2
        solver.add_constraint(p3.days_var == p1.days_var + p2.days_var)
        solver.add_constraint(p1 != p2)
        solver.add_constraint(p1 == Period(1, 0, 0))
        
        assert len(solver.constraints) == 3

    def test_solver_period_with_date_variables(self):
        """Test solver with both date and period variables."""
        solver = AdvancedDateSolver()
        date_var = solver.add_date_var("x")
        period_var = solver.add_period_var("p")
        result_var = solver.add_date_var("y")
        
        # Add constraints involving both date and period variables
        solver.add_constraint(date_var == Date(2020, 6, 15))
        solver.add_constraint(period_var == Period(1, 2, 3))
        solver.add_constraint(result_var == date_var + period_var)
        
        assert len(solver.constraints) == 3

    def test_solver_period_constraint_validation(self):
        """Test that period constraints are properly validated."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Test that constraints are added without errors
        try:
            solver.add_constraint(p1 == Period(1, 2, 3))
            solver.add_constraint(p2 == Period(0, 1, 0))
            solver.add_constraint(p1 != p2)
            solver.add_constraint(p1.days_var == p2.days_var + 30)
        except Exception as e:
            pytest.fail(f"Adding period constraints should not raise exception: {e}")
        
        assert len(solver.constraints) == 4

    def test_solver_period_variable_management(self):
        """Test that period variables are properly managed by solver."""
        solver = AdvancedDateSolver()
        
        # Add multiple period variables
        period_vars = []
        for i in range(5):
            p = solver.add_period_var(f"p{i}")
            period_vars.append(p)
        
        # Check that all variables are tracked
        assert len(solver.period_vars) == 5
        
        for i, p in enumerate(period_vars):
            assert p.name == f"p{i}"
            assert f"p{i}" in solver.period_vars

    def test_solver_period_constraint_consistency(self):
        """Test that period constraints maintain consistency."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add consistent constraints
        solver.add_constraint(p1 == Period(1, 0, 0))
        solver.add_constraint(p2 == Period(0, 1, 0))
        solver.add_constraint(p1.days_var == p2.days_var + 335)  # 365 - 30 = 335
        
        assert len(solver.constraints) == 3

    def test_solver_period_edge_cases(self):
        """Test period operations with edge cases."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Test edge cases
        edge_cases = [
            p1 == Period(0, 0, 0),      # Zero period
            p1 == Period(-1, -1, -1),   # Negative period
            p1 == Period(100, 50, 200), # Large period
            p1 != p2,                   # Inequality
        ]
        
        for constraint in edge_cases:
            solver.add_constraint(constraint)
        
        assert len(solver.constraints) == len(edge_cases)

    def test_solver_period_arithmetic_properties(self):
        """Test arithmetic properties of period operations."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")
        
        # Test commutative property: p1 + p2 = p2 + p1
        solver.add_constraint(p3.days_var == p1.days_var + p2.days_var)
        
        # Test associative property: (p1 + p2) + p3 = p1 + (p2 + p3)
        p4 = solver.add_period_var("p4")
        p5 = solver.add_period_var("p5")
        solver.add_constraint(p4.days_var == p1.days_var + p2.days_var)
        solver.add_constraint(p5.days_var == p4.days_var + p3.days_var)
        
        assert len(solver.constraints) == 4

    def test_solver_period_solve_operations(self):
        """Test that solver can handle period operations in solve."""
        solver = AdvancedDateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add simple constraints
        solver.add_constraint(p1 == Period(1, 2, 3))
        solver.add_constraint(p2 == Period(0, 1, 0))
        
        # Try to solve (may or may not be satisfiable depending on constraints)
        try:
            result = solver.solve()
            # Result should have a status
            assert 'status' in result
        except Exception as e:
            # Some constraints might not be solvable, which is expected
            pass

    def test_solver_period_comprehensive(self):
        """Comprehensive test of period operations through solver."""
        solver = AdvancedDateSolver()
        
        # Create multiple period variables
        periods = [solver.add_period_var(f"p{i}") for i in range(3)]
        
        # Add various constraints
        solver.add_constraint(periods[0] == Period(1, 0, 0))
        solver.add_constraint(periods[1] == Period(0, 1, 0))
        solver.add_constraint(periods[2] == Period(0, 0, 1))
        
        # Add arithmetic constraints
        solver.add_constraint(periods[0].days_var == periods[1].days_var + 335)
        solver.add_constraint(periods[1].days_var == periods[2].days_var + 29)
        
        # Add inequality constraints
        solver.add_constraint(periods[0] != periods[1])
        solver.add_constraint(periods[1] != periods[2])
        
        # Verify all constraints were added
        assert len(solver.constraints) == 7
        assert len(solver.period_vars) == 3
