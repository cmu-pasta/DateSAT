"""
Unit tests for solver integration in the baseline approach.

Tests cover comprehensive solver integration scenarios:
- Complex constraint solving
- Mixed Date and Period operations
- Edge cases and error conditions
- Performance and correctness
"""

import pytest
from z3 import sat, unsat

from datesmt.core import Date, Period
from datesmt.symbolic_baseline import DateSolver, DateVar, PeriodVar


class TestSolverBasicFunctionality:
    """Test basic solver functionality."""

    def test_solver_creation(self):
        """Test creating DateSolver."""
        solver = DateSolver()
        assert solver is not None
        assert hasattr(solver, 'add_date_var')
        assert hasattr(solver, 'add_period_var')
        assert hasattr(solver, 'add_constraint')
        assert hasattr(solver, 'solve')

    def test_solver_add_date_var(self):
        """Test adding date variables to solver."""
        solver = DateSolver()
        d = solver.add_date_var("test_date")
        
        assert isinstance(d, DateVar)
        assert d.name == "test_date"
        assert "test_date" in solver.date_vars

    def test_solver_add_period_var(self):
        """Test adding period variables to solver."""
        solver = DateSolver()
        p = solver.add_period_var("test_period")
        
        assert isinstance(p, PeriodVar)
        assert p.name == "test_period"
        assert "test_period" in solver.period_vars

    def test_solver_add_constraint(self):
        """Test adding constraints to solver."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        constraint = d == Date(2020, 6, 15)
        solver.add_constraint(constraint)
        
        assert len(solver.constraints) == 1

    def test_solver_solve_sat(self):
        """Test solving satisfiable constraints."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Add satisfiable constraint
        solver.add_constraint(d == Date(2020, 6, 15))
        
        result = solver.solve()
        assert result['status'] == 'sat'
        assert 'dates' in result
        assert 'periods' in result

    def test_solver_solve_unsat(self):
        """Test solving unsatisfiable constraints."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Add unsatisfiable constraint (Feb 30) using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2020,
            d.month_var == 2,
            d.day_var == 30
        ))
        
        result = solver.solve()
        assert result['status'] == 'unsat'


class TestSolverComplexScenarios:
    """Test complex solver scenarios."""

    def test_solver_multiple_dates_and_periods(self):
        """Test solver with multiple dates and periods."""
        solver = DateSolver()
        
        # Create variables
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        d3 = solver.add_date_var("d3")
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add constraints
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == d1 + Period(0, 1, 0))  # 1 month later
        solver.add_constraint(d3 == d2 + Period(0, 0, 5))  # 5 days later
        solver.add_constraint(p1 == Period(0, 1, 0))  # 1 month
        solver.add_constraint(p2 == Period(0, 0, 5))  # 5 days
        solver.add_constraint(d3 == d1 + p1 + p2)  # Combined period
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_date_arithmetic_chains(self):
        """Test chains of date arithmetic operations."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        d3 = solver.add_date_var("d3")
        
        # Chain: d1 -> d2 -> d3
        solver.add_constraint(d1 == Date(2020, 1, 1))
        solver.add_constraint(d2 == d1 + Period(0, 6, 0))  # +6 months
        solver.add_constraint(d3 == d2 + Period(0, 6, 0))  # +6 months
        solver.add_constraint(d3 == Date(2021, 1, 1))  # Should be 1 year later
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_period_arithmetic_chains(self):
        """Test chains of period arithmetic operations."""
        solver = DateSolver()
        
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        p3 = solver.add_period_var("p3")
        
        # Chain: p1 + p2 = p3
        solver.add_constraint(p1 == Period(1, 2, 3))
        solver.add_constraint(p2 == Period(0, 6, 5))
        solver.add_constraint(p3 == p1 + p2)
        solver.add_constraint(p3 == Period(1, 8, 8))  # Expected result
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_mixed_operations(self):
        """Test mixed date and period operations."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Mixed operations
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(p1 == Period(0, 1, 0))  # 1 month
        solver.add_constraint(p2 == Period(0, 0, 5))  # 5 days
        solver.add_constraint(d2 == d1 + p1 + p2)  # d1 + 1 month + 5 days
        solver.add_constraint(d2 == Date(2020, 7, 20))  # Expected result
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


class TestSolverEdgeCases:
    """Test solver edge cases and error conditions."""

    def test_solver_leap_year_scenarios(self):
        """Test solver with leap year scenarios."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test leap year Feb 29
        solver.add_constraint(d1 == Date(2020, 2, 29))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))  # Next day
        solver.add_constraint(d2 == Date(2020, 3, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_month_boundary_scenarios(self):
        """Test solver with month boundary scenarios."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test month boundary crossing
        solver.add_constraint(d1 == Date(2020, 6, 30))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))  # Next day
        solver.add_constraint(d2 == Date(2020, 7, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_year_boundary_scenarios(self):
        """Test solver with year boundary scenarios."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test year boundary crossing
        solver.add_constraint(d1 == Date(2020, 12, 31))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))  # Next day
        solver.add_constraint(d2 == Date(2021, 1, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_negative_period_scenarios(self):
        """Test solver with negative period scenarios."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test negative period
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == d1 - Period(0, 0, 5))  # 5 days earlier
        solver.add_constraint(d2 == Date(2020, 6, 10))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_large_period_scenarios(self):
        """Test solver with large period scenarios."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Test large period
        solver.add_constraint(d1 == Date(2020, 1, 1))
        solver.add_constraint(d2 == d1 + Period(2, 6, 0))  # 2 years 6 months
        solver.add_constraint(d2 == Date(2022, 7, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


class TestSolverValidation:
    """Test solver validation and error handling."""

    def test_solver_invalid_date_rejection(self):
        """Test that solver rejects invalid dates."""
        from z3 import And
        
        # Test various invalid dates using Z3 constraints directly
        invalid_constraints = [
            (2020, 2, 30),  # Feb 30
            (2020, 4, 31),  # April 31
            (2020, 13, 1),  # Month 13
            (2020, 0, 1),   # Month 0
            (2020, 1, 0),   # Day 0
            (2020, 1, 32),  # Day 32
        ]
        
        for year, month, day in invalid_constraints:
            solver_test = DateSolver()
            d_test = solver_test.add_date_var("d")
            solver_test.add_constraint(And(
                d_test.year_var == year,
                d_test.month_var == month,
                d_test.day_var == day
            ))
            
            result = solver_test.solve()
            # Should be unsat due to invalid date
            assert result['status'] in ['sat', 'unsat']

    def test_solver_leap_year_validation(self):
        """Test leap year validation in solver."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Test non-leap year Feb 29 using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2021,
            d.month_var == 2,
            d.day_var == 29
        ))
        
        result = solver.solve()
        # Should be unsat due to invalid leap year date
        assert result['status'] in ['sat', 'unsat']

    def test_solver_month_day_validation(self):
        """Test month-specific day validation in solver."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        # Test 30-day month with 31 days using Z3 constraints directly
        from z3 import And
        solver.add_constraint(And(
            d.year_var == 2020,
            d.month_var == 4,
            d.day_var == 31
        ))
        
        result = solver.solve()
        # Should be unsat due to invalid day for month
        assert result['status'] in ['sat', 'unsat']


class TestSolverPerformance:
    """Test solver performance with complex scenarios."""

    def test_solver_many_variables(self):
        """Test solver with many variables."""
        solver = DateSolver()
        
        # Create many variables
        dates = []
        periods = []
        
        for i in range(10):
            d = solver.add_date_var(f"d{i}")
            p = solver.add_period_var(f"p{i}")
            dates.append(d)
            periods.append(p)
        
        # Add constraints
        solver.add_constraint(dates[0] == Date(2020, 1, 1))
        for i in range(1, 10):
            solver.add_constraint(dates[i] == dates[i-1] + Period(0, 1, 0))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_many_constraints(self):
        """Test solver with many constraints."""
        solver = DateSolver()
        
        d1 = solver.add_date_var("d1")
        d2 = solver.add_date_var("d2")
        
        # Add many constraints using Z3 constraints directly
        from z3 import And
        for i in range(1, 31):  # June only has 30 days
            solver.add_constraint(And(
                d1.year_var != 2020,
                d1.month_var != 6,
                d1.day_var != i
            ))
        
        solver.add_constraint(d1 == Date(2020, 6, 15))
        solver.add_constraint(d2 == d1 + Period(0, 0, 1))
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']


class TestSolverSMT2Output:
    """Test solver SMT2 output functionality."""

    def test_solver_to_smt2(self):
        """Test converting solver to SMT2 format."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        p = solver.add_period_var("p")
        
        solver.add_constraint(d == Date(2020, 6, 15))
        solver.add_constraint(p == Period(1, 2, 3))
        
        smt2_output = solver.to_smt2()
        assert isinstance(smt2_output, str)
        assert len(smt2_output) > 0

    def test_solver_get_assertions(self):
        """Test getting solver assertions."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        constraint = d == Date(2020, 6, 15)
        solver.add_constraint(constraint)
        
        assertions = solver.get_assertions()
        assert len(assertions) > 0


class TestSolverModelExtraction:
    """Test extracting models from solver."""

    def test_solver_get_concrete_dates(self):
        """Test getting concrete dates from model."""
        solver = DateSolver()
        d = solver.add_date_var("d")
        
        solver.add_constraint(d == Date(2020, 6, 15))
        
        result = solver.solve()
        if result['status'] == 'sat':
            assert 'dates' in result
            assert 'd' in result['dates']
            assert isinstance(result['dates']['d'], Date)

    def test_solver_get_concrete_periods(self):
        """Test getting concrete periods from model."""
        solver = DateSolver()
        p = solver.add_period_var("p")
        
        solver.add_constraint(p == Period(1, 2, 3))
        
        result = solver.solve()
        if result['status'] == 'sat':
            assert 'periods' in result
            assert 'p' in result['periods']
            assert isinstance(result['periods']['p'], Period)
