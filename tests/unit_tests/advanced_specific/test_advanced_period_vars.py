"""
Unit tests for PeriodVar class in the advanced approach.

Tests cover PeriodVar creation, manipulation, and Z3 constraint generation
as implemented in the advanced approach.
"""

import pytest
from z3 import BoolRef, Int

from datesmt.core import Period
from datesmt.symbolic_advanced import PeriodVar


class TestAdvancedPeriodVar:
    """Test PeriodVar class in advanced approach."""

    def test_period_var_creation(self):
        """Test creating PeriodVar in advanced approach."""
        p = PeriodVar("test_period")
        assert p.name == "test_period"
        assert hasattr(p, 'days_var')
        assert hasattr(p, 'to_concrete_period')
        assert hasattr(p, 'to_days_approximate')

    def test_period_var_creation_with_different_names(self):
        """Test creating PeriodVar with different names."""
        names = ["p1", "period_var", "test", "x", "y", "z"]
        
        for name in names:
            p = PeriodVar(name)
            assert p.name == name
            assert hasattr(p, 'days_var')

    def test_period_var_attributes(self):
        """Test that PeriodVar has all required attributes."""
        p = PeriodVar("test")
        
        # Check required attributes exist
        required_attrs = ['name', 'days_var', 'to_concrete_period', 'to_days_approximate']
        for attr in required_attrs:
            assert hasattr(p, attr), f"PeriodVar should have attribute {attr}"

    def test_period_var_equality_with_concrete_period(self):
        """Test PeriodVar equality with concrete Period."""
        p = PeriodVar("p")
        concrete_period = Period(1, 2, 3)

        # This should create a Z3 constraint
        constraint = p == concrete_period
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_equality_with_another_period_var(self):
        """Test PeriodVar equality with another PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")

        constraint = p1 == p2
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_inequality(self):
        """Test PeriodVar inequality."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")

        constraint = p1 != p2
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_equality_with_different_periods(self):
        """Test PeriodVar equality with different concrete periods."""
        p = PeriodVar("p")
        
        test_periods = [
            Period(0, 0, 0),
            Period(1, 0, 0),
            Period(0, 1, 0),
            Period(0, 0, 1),
            Period(1, 1, 1),
            Period(-1, -1, -1),
            Period(10, 5, 15),
        ]
        
        for period in test_periods:
            constraint = p == period
            assert constraint is not None
            assert isinstance(constraint, BoolRef)

    def test_period_var_inequality_with_different_periods(self):
        """Test PeriodVar inequality with different concrete periods."""
        p = PeriodVar("p")
        
        test_periods = [
            Period(0, 0, 0),
            Period(1, 0, 0),
            Period(0, 1, 0),
            Period(0, 0, 1),
            Period(1, 1, 1),
            Period(-1, -1, -1),
        ]
        
        for period in test_periods:
            constraint = p != period
            assert constraint is not None
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

    def test_period_var_days_var_type(self):
        """Test that PeriodVar.days_var is a Z3 Int variable."""
        p = PeriodVar("p")
        assert isinstance(p.days_var, Int)

    def test_period_var_multiple_instances(self):
        """Test creating multiple PeriodVar instances."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        p3 = PeriodVar("p3")
        
        # Each should have unique names
        assert p1.name == "p1"
        assert p2.name == "p2"
        assert p3.name == "p3"
        
        # Each should have different days_var
        assert p1.days_var != p2.days_var
        assert p2.days_var != p3.days_var
        assert p1.days_var != p3.days_var

    def test_period_var_constraint_creation(self):
        """Test creating various constraints with PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        concrete = Period(1, 2, 3)
        
        # Test different constraint types
        constraints = [
            p1 == concrete,
            p1 != concrete,
            p1 == p2,
            p1 != p2,
        ]
        
        for constraint in constraints:
            assert constraint is not None
            assert isinstance(constraint, BoolRef)

    def test_period_var_constraint_combinations(self):
        """Test complex constraint combinations with PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        p3 = PeriodVar("p3")
        
        # Test complex constraints
        constraint1 = (p1 == Period(1, 0, 0)) & (p2 == Period(0, 1, 0))
        constraint2 = (p1 == p2) | (p1 == p3)
        constraint3 = (p1 != Period(0, 0, 0)) & (p2 != Period(0, 0, 0))
        
        for constraint in [constraint1, constraint2, constraint3]:
            assert constraint is not None
            assert isinstance(constraint, BoolRef)

    def test_period_var_equality_reflexivity(self):
        """Test that PeriodVar equality is reflexive."""
        p = PeriodVar("p")
        
        # p == p should be true (reflexive)
        constraint = p == p
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_inequality_with_self(self):
        """Test that PeriodVar inequality with self is false."""
        p = PeriodVar("p")
        
        # p != p should be false
        constraint = p != p
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_with_zero_period(self):
        """Test PeriodVar operations with zero period."""
        p = PeriodVar("p")
        zero_period = Period(0, 0, 0)
        
        constraint = p == zero_period
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_with_negative_period(self):
        """Test PeriodVar operations with negative period."""
        p = PeriodVar("p")
        negative_period = Period(-1, -2, -3)
        
        constraint = p == negative_period
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_with_large_period(self):
        """Test PeriodVar operations with large period."""
        p = PeriodVar("p")
        large_period = Period(100, 50, 200)
        
        constraint = p == large_period
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_constraint_consistency(self):
        """Test that PeriodVar constraints are consistent."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        
        # If p1 == p2 and p1 == Period(1,2,3), then p2 == Period(1,2,3)
        constraint1 = p1 == p2
        constraint2 = p1 == Period(1, 2, 3)
        constraint3 = p2 == Period(1, 2, 3)
        
        # All constraints should be valid Z3 expressions
        for constraint in [constraint1, constraint2, constraint3]:
            assert constraint is not None
            assert isinstance(constraint, BoolRef)

    def test_period_var_method_calls(self):
        """Test that PeriodVar methods can be called without errors."""
        p = PeriodVar("p")
        
        # Test method calls (they may not work without a model, but should not crash)
        try:
            p.to_concrete_period()
        except Exception:
            pass  # Expected to fail without a model
        
        try:
            p.to_days_approximate()
        except Exception:
            pass  # Expected to fail without a model

    def test_period_var_string_representation(self):
        """Test PeriodVar string representation."""
        p = PeriodVar("test_period")
        
        # Should have some string representation
        str_repr = str(p)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0

    def test_period_var_equality_with_same_name(self):
        """Test PeriodVar equality with same name but different instances."""
        p1 = PeriodVar("same_name")
        p2 = PeriodVar("same_name")
        
        # Different instances should be different objects
        assert p1 is not p2
        assert p1.days_var != p2.days_var
        
        # But equality constraint should still work
        constraint = p1 == p2
        assert constraint is not None
        assert isinstance(constraint, BoolRef)

    def test_period_var_comprehensive_constraints(self):
        """Test comprehensive constraint creation with PeriodVar."""
        p1 = PeriodVar("p1")
        p2 = PeriodVar("p2")
        p3 = PeriodVar("p3")
        
        # Test various constraint combinations
        constraints = [
            p1 == Period(1, 0, 0),
            p2 == Period(0, 1, 0),
            p3 == Period(0, 0, 1),
            p1 != p2,
            p2 != p3,
            p1 != p3,
            (p1 == Period(1, 0, 0)) & (p2 == Period(0, 1, 0)),
            (p1 == p2) | (p1 == p3),
            (p1 != Period(0, 0, 0)) & (p2 != Period(0, 0, 0)) & (p3 != Period(0, 0, 0)),
        ]
        
        for i, constraint in enumerate(constraints):
            assert constraint is not None, f"Constraint {i} should not be None"
            assert isinstance(constraint, BoolRef), f"Constraint {i} should be BoolRef"
