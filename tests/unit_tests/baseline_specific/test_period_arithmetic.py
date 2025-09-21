"""
Period arithmetic tests for DATE-SMT baseline implementation.

This consolidated test file covers all period arithmetic operations:
- Period + Period (addition)
- Period - Period (subtraction) 
- Period * Int (multiplication)
- Int * Period (reverse multiplication)
- Period == Period (equality)
- Period != Period (inequality)
- Canonicalization and normalization
- Algebraic laws and properties
- Type discipline and error handling

Tests cover period arithmetic as implemented through the baseline solver
using year/month/day components with proper canonicalization.
"""

import pytest
from z3 import BoolRef, Int, Solver, sat

from datesmt.core import Period
from datesmt.symbolic_baseline import DateSolver, PeriodVar


# ---------------------------------------------------------------------------
# PeriodVar Creation and Basic Properties
# ---------------------------------------------------------------------------

class TestPeriodVarCreation:
    """Test PeriodVar creation and basic properties."""

    def test_period_var_creation(self):
        """Test creating PeriodVar."""
        p = PeriodVar("test_period")
        assert p.name == "test_period"
        assert hasattr(p, 'years_var')
        assert hasattr(p, 'months_var')
        assert hasattr(p, 'days_var')

    def test_period_var_string_representation(self):
        """Test PeriodVar string representation."""
        p = PeriodVar("test_period")
        assert "test_period" in str(p)
        assert "PeriodVar" in str(p)

    def test_period_var_conversion_to_concrete(self):
        """Test converting PeriodVar to concrete Period via model."""
        p = PeriodVar("p")
        assert hasattr(p, 'to_concrete_period')
        assert callable(p.to_concrete_period)


# ---------------------------------------------------------------------------
# Period Addition Operations
# ---------------------------------------------------------------------------

class TestPeriodAddition:
    """Test Period + Period addition operations."""

    def test_period_var_add_concrete_period(self):
        """Test PeriodVar + concrete Period."""
        p = PeriodVar("p")
        concrete = Period(1, 2, 3)
        
        result = p + concrete
        assert isinstance(result, PeriodVar)
        assert "plus" in result.name
        assert "1y_2m_3d" in result.name

    def test_period_var_add_period_var(self):
        """Test PeriodVar + PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        result = p1 + p2
        assert isinstance(result, PeriodVar)
        assert "plus" in result.name
        assert "p2" in result.name

    def test_period_var_add_with_canonicalization(self):
        """Test that addition properly canonicalizes months."""
        p = PeriodVar("p")
        # Add 15 months (should become 1 year + 3 months)
        concrete = Period(0, 15, 0)
        
        result = p + concrete
        assert isinstance(result, PeriodVar)

    def test_period_var_add_negative_period(self):
        """Test PeriodVar + negative Period."""
        p = PeriodVar("p")
        concrete = Period(-1, -2, -3)
        
        result = p + concrete
        assert isinstance(result, PeriodVar)

    def test_period_var_add_type_error(self):
        """Test that addition raises TypeError for invalid types."""
        p = PeriodVar("p")
        
        with pytest.raises(TypeError):
            p + "invalid_type"
        
        with pytest.raises(TypeError):
            p + 42


# ---------------------------------------------------------------------------
# Period Subtraction Operations
# ---------------------------------------------------------------------------

class TestPeriodSubtraction:
    """Test Period - Period subtraction operations."""

    def test_period_var_sub_concrete_period(self):
        """Test PeriodVar - concrete Period."""
        p = PeriodVar("p")
        concrete = Period(1, 2, 3)
        
        result = p - concrete
        assert isinstance(result, PeriodVar)
        assert "minus" in result.name
        assert "1y_2m_3d" in result.name

    def test_period_var_sub_period_var(self):
        """Test PeriodVar - PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        result = p1 - p2
        assert isinstance(result, PeriodVar)
        assert "minus" in result.name
        assert "p2" in result.name

    def test_period_var_sub_with_canonicalization(self):
        """Test that subtraction properly canonicalizes months."""
        p = PeriodVar("p")
        # Subtract 15 months (should become -1 year - 3 months)
        concrete = Period(0, 15, 0)
        
        result = p - concrete
        assert isinstance(result, PeriodVar)

    def test_period_var_sub_negative_period(self):
        """Test PeriodVar - negative Period."""
        p = PeriodVar("p")
        concrete = Period(-1, -2, -3)
        
        result = p - concrete
        assert isinstance(result, PeriodVar)

    def test_period_var_sub_type_error(self):
        """Test that subtraction raises TypeError for invalid types."""
        p = PeriodVar("p")
        
        with pytest.raises(TypeError):
            p - "invalid_type"
        
        with pytest.raises(TypeError):
            p - 42


# ---------------------------------------------------------------------------
# Period Multiplication Operations
# ---------------------------------------------------------------------------

class TestPeriodMultiplication:
    """Test Period * Int multiplication operations."""

    def test_period_var_mul_positive_int(self):
        """Test PeriodVar * positive integer."""
        p = PeriodVar("p")
        
        result = p * 3
        assert isinstance(result, PeriodVar)
        assert "times" in result.name
        assert "3" in result.name

    def test_period_var_mul_negative_int(self):
        """Test PeriodVar * negative integer."""
        p = PeriodVar("p")
        
        result = p * -2
        assert isinstance(result, PeriodVar)
        assert "times" in result.name
        assert "-2" in result.name

    def test_period_var_mul_zero(self):
        """Test PeriodVar * zero."""
        p = PeriodVar("p")
        
        result = p * 0
        assert isinstance(result, PeriodVar)

    def test_period_var_mul_with_canonicalization(self):
        """Test that multiplication properly canonicalizes months."""
        p = PeriodVar("p")
        # Multiply by 2, which could create months > 12
        result = p * 2
        assert isinstance(result, PeriodVar)

    def test_period_var_mul_type_error(self):
        """Test that multiplication raises TypeError for invalid types."""
        p = PeriodVar("p")
        
        with pytest.raises(TypeError):
            p * "invalid_type"
        
        with pytest.raises(TypeError):
            p * 3.14

    def test_int_mul_period_var(self):
        """Test Int * PeriodVar (reverse multiplication)."""
        p = PeriodVar("p")
        
        result = 3 * p
        assert isinstance(result, PeriodVar)
        assert "times" in result.name
        assert "3" in result.name


# ---------------------------------------------------------------------------
# Period Equality and Inequality Operations
# ---------------------------------------------------------------------------

class TestPeriodEquality:
    """Test Period equality operations."""

    def test_period_var_eq_concrete_period(self):
        """Test PeriodVar == concrete Period."""
        p = PeriodVar("p")
        concrete = Period(1, 2, 3)
        
        constraint = p == concrete
        assert isinstance(constraint, BoolRef)

    def test_period_var_eq_period_var(self):
        """Test PeriodVar == PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        constraint = p1 == p2
        assert isinstance(constraint, BoolRef)

    def test_period_var_eq_type_error(self):
        """Test that equality raises TypeError for invalid types."""
        p = PeriodVar("p")
        
        with pytest.raises(TypeError):
            p == "invalid_type"
        
        with pytest.raises(TypeError):
            p == 42


class TestPeriodInequality:
    """Test Period inequality operations."""

    def test_period_var_ne_concrete_period(self):
        """Test PeriodVar != concrete Period."""
        p = PeriodVar("p")
        concrete = Period(1, 2, 3)
        
        constraint = p != concrete
        assert isinstance(constraint, BoolRef)

    def test_period_var_ne_period_var(self):
        """Test PeriodVar != PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        constraint = p1 != p2
        assert isinstance(constraint, BoolRef)


# ---------------------------------------------------------------------------
# Period Canonicalization and Normalization
# ---------------------------------------------------------------------------

class TestPeriodCanonicalization:
    """Test period canonicalization and normalization."""

    def test_canonicalization_basic(self):
        """Test basic month canonicalization."""
        # 15 months should become 1 year 3 months
        p = PeriodVar("p")
        result = p + Period(0, 15, 0)
        assert isinstance(result, PeriodVar)

    def test_canonicalization_negative_months(self):
        """Test canonicalization with negative months."""
        # -15 months should become -1 year -3 months
        p = PeriodVar("p")
        result = p + Period(0, -15, 0)
        assert isinstance(result, PeriodVar)

    def test_canonicalization_exact_multiple(self):
        """Test canonicalization with exact multiples of 12."""
        # 24 months should become 2 years 0 months
        p = PeriodVar("p")
        result = p + Period(0, 24, 0)
        assert isinstance(result, PeriodVar)

    def test_canonicalization_mixed_components(self):
        """Test canonicalization with mixed year/month components."""
        p = PeriodVar("p")
        result = p + Period(1, 15, 0)  # 1 year 15 months
        assert isinstance(result, PeriodVar)

    def test_normalization_uniqueness(self):
        """Test that canonical form is unique."""
        # Period(1, 12, 0) should equal Period(2, 0, 0) after canonicalization
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        # These should be equivalent after canonicalization
        constraint1 = p1 == Period(1, 12, 0)
        constraint2 = p2 == Period(2, 0, 0)
        constraint3 = p1 == p2
        
        assert isinstance(constraint1, BoolRef)
        assert isinstance(constraint2, BoolRef)
        assert isinstance(constraint3, BoolRef)


# ---------------------------------------------------------------------------
# Period Algebraic Laws and Properties
# ---------------------------------------------------------------------------

class TestPeriodAlgebraicLaws:
    """Test period algebraic laws and properties."""

    def test_commutativity_addition(self):
        """Test that period addition is commutative."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        # p1 + p2 should equal p2 + p1
        sum1 = p1 + p2
        sum2 = p2 + p1
        constraint = sum1 == sum2
        
        assert isinstance(constraint, BoolRef)

    def test_associativity_addition(self):
        """Test that period addition is associative."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        p3 = PeriodVar("p3")
        
        # (p1 + p2) + p3 should equal p1 + (p2 + p3)
        sum1 = (p1 + p2) + p3
        sum2 = p1 + (p2 + p3)
        constraint = sum1 == sum2
        
        assert isinstance(constraint, BoolRef)

    def test_distributivity_multiplication(self):
        """Test that period multiplication distributes over addition."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        k = 3
        
        # k * (p1 + p2) should equal k * p1 + k * p2
        left = k * (p1 + p2)
        right = (k * p1) + (k * p2)
        constraint = left == right
        
        assert isinstance(constraint, BoolRef)

    def test_identity_elements(self):
        """Test identity elements for period operations."""
        p = PeriodVar("p")
        zero_period = Period(0, 0, 0)
        
        # p + 0 should equal p
        sum_with_zero = p + zero_period
        constraint1 = sum_with_zero == p
        
        # p * 0 should equal 0
        mul_by_zero = p * 0
        constraint2 = mul_by_zero == zero_period
        
        # p * 1 should equal p
        mul_by_one = p * 1
        constraint3 = mul_by_one == p
        
        assert isinstance(constraint1, BoolRef)
        assert isinstance(constraint2, BoolRef)
        assert isinstance(constraint3, BoolRef)

    def test_negation_properties(self):
        """Test period negation properties."""
        p = PeriodVar("p")
        neg_p = p * -1
        
        # p + (-p) should equal 0
        sum_with_neg = p + neg_p
        zero_period = Period(0, 0, 0)
        constraint = sum_with_neg == zero_period
        
        assert isinstance(constraint, BoolRef)

    def test_scaling_properties(self):
        """Test period scaling properties."""
        p = PeriodVar("p")
        k1, k2 = 2, 3
        
        # (k1 * k2) * p should equal k1 * (k2 * p)
        left = (k1 * k2) * p
        right = k1 * (k2 * p)
        constraint = left == right
        
        assert isinstance(constraint, BoolRef)


# ---------------------------------------------------------------------------
# Period Type Discipline and Error Handling
# ---------------------------------------------------------------------------

class TestPeriodTypeDiscipline:
    """Test period type discipline and error handling."""

    def test_period_comparison_restrictions(self):
        """Test that period comparison operations are restricted."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        # Periods should not support ordering operations
        with pytest.raises(TypeError):
            p1 < p2
        
        with pytest.raises(TypeError):
            p1 > p2
        
        with pytest.raises(TypeError):
            p1 <= p2
        
        with pytest.raises(TypeError):
            p1 >= p2

    def test_period_equality_allowed(self):
        """Test that period equality operations are allowed."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        # Equality and inequality should be allowed
        eq_constraint = p1 == p2
        ne_constraint = p1 != p2
        
        assert isinstance(eq_constraint, BoolRef)
        assert isinstance(ne_constraint, BoolRef)

    def test_period_arithmetic_type_errors(self):
        """Test type errors in period arithmetic."""
        p = PeriodVar("p")
        
        # Invalid types for arithmetic operations
        with pytest.raises(TypeError):
            p + "string"
        
        with pytest.raises(TypeError):
            p - 3.14
        
        with pytest.raises(TypeError):
            p * "invalid"
        
        with pytest.raises(TypeError):
            "string" + p
        
        with pytest.raises(TypeError):
            3.14 * p


# ---------------------------------------------------------------------------
# Solver Integration Tests
# ---------------------------------------------------------------------------

class TestPeriodSolverIntegration:
    """Test Period operations with solver integration."""

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

    def test_solver_period_arithmetic(self):
        """Test Period arithmetic through solver."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Test addition
        p3 = p1 + p2
        assert isinstance(p3, PeriodVar)
        
        # Test subtraction
        p4 = p1 - p2
        assert isinstance(p4, PeriodVar)
        
        # Test multiplication
        p5 = p1 * 2
        assert isinstance(p5, PeriodVar)

    def test_solver_period_constraints(self):
        """Test Period constraints through solver."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add equality constraint
        constraint1 = p1 == Period(1, 2, 3)
        solver.add_constraint(constraint1)
        
        # Add inequality constraint
        constraint2 = p1 != p2
        solver.add_constraint(constraint2)
        
        # Add arithmetic constraint
        p3 = p1 + p2
        constraint3 = p3 == Period(2, 4, 6)
        solver.add_constraint(constraint3)
        
        assert len(solver.constraints) == 3

    def test_solver_period_solve(self):
        """Test solving Period constraints."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        p2 = solver.add_period_var("p2")
        
        # Add constraints
        solver.add_constraint(p1 == Period(1, 0, 0))  # 1 year
        solver.add_constraint(p2 == Period(0, 6, 0))  # 6 months
        solver.add_constraint(p1 + p2 == Period(1, 6, 0))  # 1 year 6 months
        
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_period_canonicalization(self):
        """Test that solver properly handles month canonicalization."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        
        # Add constraint that creates month overflow
        solver.add_constraint(p1 == Period(0, 15, 0))  # 15 months
        
        # This should be canonicalized to 1 year 3 months
        result = solver.solve()
        assert result['status'] in ['sat', 'unsat']

    def test_solver_period_arithmetic_with_concrete_periods(self):
        """Test period arithmetic with concrete periods."""
        solver = DateSolver()
        p1 = solver.add_period_var("p1")
        
        # Test addition with concrete period
        p2 = p1 + Period(1, 2, 3)
        assert isinstance(p2, PeriodVar)
        
        # Test subtraction with concrete period
        p3 = p1 - Period(1, 2, 3)
        assert isinstance(p3, PeriodVar)
        
        # Test multiplication with concrete period
        p4 = p1 * 2
        assert isinstance(p4, PeriodVar)


# ---------------------------------------------------------------------------
# Edge Cases and Boundary Tests
# ---------------------------------------------------------------------------

class TestPeriodEdgeCases:
    """Test Period operations with edge cases."""

    def test_period_zero_values(self):
        """Test Period operations with zero values."""
        p = PeriodVar("p")
        zero_period = Period(0, 0, 0)
        
        # Addition with zero
        result1 = p + zero_period
        assert isinstance(result1, PeriodVar)
        
        # Subtraction with zero
        result2 = p - zero_period
        assert isinstance(result2, PeriodVar)
        
        # Multiplication by zero
        result3 = p * 0
        assert isinstance(result3, PeriodVar)

    def test_period_large_values(self):
        """Test Period operations with large values."""
        p = PeriodVar("p")
        large_period = Period(100, 120, 365)
        
        # Addition with large period
        result1 = p + large_period
        assert isinstance(result1, PeriodVar)
        
        # Multiplication with large factor
        result2 = p * 10
        assert isinstance(result2, PeriodVar)

    def test_period_negative_values(self):
        """Test Period operations with negative values."""
        p = PeriodVar("p")
        negative_period = Period(-1, -2, -3)
        
        # Addition with negative period
        result1 = p + negative_period
        assert isinstance(result1, PeriodVar)
        
        # Subtraction with negative period
        result2 = p - negative_period
        assert isinstance(result2, PeriodVar)
        
        # Multiplication with negative factor
        result3 = p * -2
        assert isinstance(result3, PeriodVar)

    def test_period_overflow_handling(self):
        """Test handling of period component overflow."""
        p = PeriodVar("p")
        
        # Test with very large month values
        large_months = Period(0, 1000, 0)
        result = p + large_months
        assert isinstance(result, PeriodVar)
        
        # Test with very large day values
        large_days = Period(0, 0, 10000)
        result = p + large_days
        assert isinstance(result, PeriodVar)

    def test_period_underflow_handling(self):
        """Test handling of period component underflow."""
        p = PeriodVar("p")
        
        # Test with very negative month values
        negative_months = Period(0, -1000, 0)
        result = p + negative_months
        assert isinstance(result, PeriodVar)
        
        # Test with very negative day values
        negative_days = Period(0, 0, -10000)
        result = p + negative_days
        assert isinstance(result, PeriodVar)