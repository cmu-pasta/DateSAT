"""
Test that intermediate DateVars created during arithmetic operations are properly bounded.
"""

import pytest
from z3 import And, Or, IntVal, sat, unsat

from datesmt.core import Date, Period
from datesmt.symbolic_int.naive_int import NaiveSolver


def test_intermediate_date_bounded_in_single_operation():
    """Test that intermediate DateVar from x + Period is bounded."""
    solver = NaiveSolver()
    x = solver.add_date_var("x")
    
    # Create intermediate DateVar: x + Period(1, 2, 3)
    # This should create an intermediate DateVar that is bounded
    y = x + Period(1, 2, 3)
    
    # Add constraint linking y to a concrete date
    solver.add_constraint(x == Date(2020, 6, 15))
    solver.add_constraint(y == Date(2021, 8, 18))
    
    # Check that the solver is satisfiable (bounds should allow this)
    result = solver.check()
    assert result == sat, "Solver should be satisfiable with valid dates"
    
    # Get assertions and check for bounds on intermediate DateVar
    assertions = solver.get_assertions()
    
    # The intermediate DateVar should have bounds constraints
    # Look for constraints that include year bounds (1901-2099) or the full bounds Or expression
    # The intermediate DateVar name should contain "plus"
    has_intermediate_bounds = False
    
    for assertion in assertions:
        # Convert to string to check for intermediate variable patterns
        assertion_str = str(assertion)
        # Check if this assertion involves an intermediate variable (contains "plus")
        if "plus" in assertion_str:
            # Check if it contains year bounds (indicating bounds were added)
            if "1901" in assertion_str or "2099" in assertion_str or "1900" in assertion_str or "2100" in assertion_str:
                has_intermediate_bounds = True
                break
    
    assert has_intermediate_bounds, "Intermediate DateVar should have bounds constraints"


def test_intermediate_date_bounded_in_multiple_operations():
    """Test that intermediate DateVars from multiple operations are bounded."""
    solver = NaiveSolver()
    x = solver.add_date_var("x")
    
    # Create multiple intermediate DateVars
    y = x + Period(1, 0, 0)  # intermediate: x_plus_1y_0m_0d
    z = y + Period(0, 2, 0)   # intermediate: x_plus_1y_0m_0d_plus_0y_2m_0d
    
    solver.add_constraint(x == Date(2020, 6, 15))
    solver.add_constraint(z == Date(2021, 8, 15))
    
    result = solver.check()
    assert result == sat, "Solver should be satisfiable"
    
    # Check that intermediate DateVars have bounds
    assertions = solver.get_assertions()
    intermediate_count = 0
    
    for assertion in assertions:
        assertion_str = str(assertion)
        if "plus" in assertion_str:
            # Check for bounds indicators
            if any(year in assertion_str for year in ["1900", "1901", "2099", "2100"]):
                intermediate_count += 1
    
    # Should have bounds for at least 2 intermediate DateVars (y and z)
    assert intermediate_count >= 2, f"Expected at least 2 intermediate DateVars with bounds, found {intermediate_count}"


def test_intermediate_date_bounds_enforce_valid_range():
    """Test that intermediate DateVar bounds prevent out-of-range dates."""
    # Test 1: Valid dates should work
    solver = NaiveSolver()
    x = solver.add_date_var("x")
    
    # Create intermediate DateVar
    y = x + Period(1, 2, 3)
    
    # Use a valid date at the start of the range
    solver.add_constraint(x == Date(1900, 3, 1))
    # y should be around 1901-05-04, which is valid
    
    result = solver.check()
    assert result == sat, "Should be satisfiable with valid dates"
    
    # Test 2: Try to force intermediate to be out of bounds (after 2100-02-28)
    solver2 = NaiveSolver()
    x2 = solver2.add_date_var("x2")
    y2 = x2 + Period(0, 0, 1) - Period(0, 0, 1)  # This would push it way past 2100
    
    solver2.add_constraint(x2 == Date(2100, 2, 28))
    # y2 would be 2200-01-01, which is out of bounds
    
    result2 = solver2.check()
    # Should be UNSAT because intermediate DateVar is bounded and out of range
    assert result2 == unsat, "Should be UNSAT when intermediate DateVar is out of bounds"
    
    # Test 3: Try to force intermediate to be out of bounds (before 1900-03-01)
    solver3 = NaiveSolver()
    x3 = solver3.add_date_var("x3")
    y3 = x3 - Period(10, 0, 0)  # Subtract 10 years
    
    solver3.add_constraint(x3 == Date(1900, 3, 1))
    # y3 would be 1890-03-01, which is out of bounds
    
    result3 = solver3.check()
    # Should be UNSAT because intermediate DateVar is bounded and out of range
    assert result3 == unsat, "Should be UNSAT when intermediate DateVar is before valid range"


def test_intermediate_date_bounded_vs_unbounded():
    """Test that bounded DateVars have bounds but unbounded ones don't."""
    # Test with bounded DateVar (created via add_date_var)
    solver_bounded = NaiveSolver()
    x_bounded = solver_bounded.add_date_var("x")
    y_bounded = x_bounded + Period(1, 0, 0)
    
    assertions_bounded = solver_bounded.get_assertions()
    bounded_count = sum(1 for a in assertions_bounded 
                       if any(year in str(a) for year in ["1900", "1901", "2099", "2100"]))
    
    # Test with unbounded DateVar (created directly)
    from datesmt.symbolic_int.naive_int import DateVar
    solver_unbounded = NaiveSolver()
    x_unbounded = DateVar("x_unbounded", bounded=False)  # Explicitly unbounded
    y_unbounded = x_unbounded + Period(1, 0, 0)
    
    # Add constraints manually
    solver_unbounded.add_constraint(x_unbounded.year == 2020)
    solver_unbounded.add_constraint(x_unbounded.month == 6)
    solver_unbounded.add_constraint(x_unbounded.day == 15)
    
    assertions_unbounded = solver_unbounded.get_assertions()
    unbounded_count = sum(1 for a in assertions_unbounded 
                          if any(year in str(a) for year in ["1900", "1901", "2099", "2100"]))
    
    # Bounded should have more bounds constraints than unbounded
    assert bounded_count > unbounded_count, \
        f"Bounded DateVars should have more bounds constraints ({bounded_count} vs {unbounded_count})"


def test_intermediate_date_bounds_preserved_in_chain():
    """Test that bounds are preserved through a chain of operations."""
    solver = NaiveSolver()
    x = solver.add_date_var("x")
    
    # Create a chain: x -> y -> z -> w
    y = x + Period(0, 1, 0)
    z = y + Period(0, 1, 0)
    w = z + Period(0, 1, 0)
    
    solver.add_constraint(x == Date(2020, 1, 15))
    solver.add_constraint(w == Date(2020, 4, 15))
    
    result = solver.check()
    assert result == sat, "Chain of operations should be satisfiable"
    
    # All intermediate DateVars (y, z, w) should be bounded
    assertions = solver.get_assertions()
    intermediate_vars_with_bounds = 0
    
    for assertion in assertions:
        assertion_str = str(assertion)
        if "plus" in assertion_str:
            if any(year in assertion_str for year in ["1900", "1901", "2099", "2100"]):
                intermediate_vars_with_bounds += 1
    
    # Should have bounds for y, z, and w (3 intermediate DateVars)
    assert intermediate_vars_with_bounds >= 3, \
        f"Expected at least 3 intermediate DateVars with bounds, found {intermediate_vars_with_bounds}"


def test_intermediate_date_bounds_in_subtraction():
    """Test that intermediate DateVar from subtraction is also bounded."""
    solver = NaiveSolver()
    x = solver.add_date_var("x")
    
    # Subtraction creates intermediate DateVar
    y = x - Period(1, 2, 3)
    
    solver.add_constraint(x == Date(2020, 6, 15))
    solver.add_constraint(y == Date(2019, 4, 12))
    
    result = solver.check()
    assert result == sat, "Subtraction should be satisfiable"
    
    # Check for bounds on intermediate DateVar
    assertions = solver.get_assertions()
    has_bounds = any(
        "plus" in str(a) and any(year in str(a) for year in ["1900", "1901", "2099", "2100"])
        for a in assertions
    )
    
    assert has_bounds, "Intermediate DateVar from subtraction should have bounds"
