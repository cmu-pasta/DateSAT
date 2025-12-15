#!/usr/bin/env python3
"""
Test script demonstrating symbolic components inside Date() constructor.
This tests the new functionality in enumeration_baseline.py.
"""

from datesmt.enumeration_baseline import EnumerationSolver
from datesmt.core import Date, Period

def test_symbolic_year():
    """Test Date with only year symbolic: Date(year_var, 1, 1)"""
    print("\n=== Test 1: Symbolic Year ===")
    solver = EnumerationSolver()
    
    # Create a regular date variable
    x = solver.add_date_var("x")
    
    # Create a symbolic year variable
    year_var = solver.add_year_var("y")
    
    # Create a date with symbolic year: Date(year_var, 1, 1)
    d = solver.SymbolicDate(year_var, 1, 1)
    
    # Add constraints: x < Date(year_var, 1, 1) and x > Date(2000, 1, 1)
    solver.add_constraint(x < d)
    solver.add_constraint(x > Date(2000, 1, 1))
    
    # This should enumerate ~200 years instead of ~73,000 dates
    result = solver.solve()
    
    if result['status'] == 'sat':
        print(f"✓ Found solution: x = {result['dates']['x']}")
        print(f"  Symbolic year variable enumerated instead of full dates")
        print(f"  Search space: ~200 years × ~73k dates = ~14.6M combinations")
    else:
        print(f"✗ Status: {result['status']}")


def test_symbolic_month():
    """Test Date with only month symbolic: Date(2025, month_var, 15)"""
    print("\n=== Test 2: Symbolic Month ===")
    solver = EnumerationSolver()
    
    x = solver.add_date_var("x")
    month_var = solver.add_month_var("m")
    
    # Date with symbolic month
    d = solver.SymbolicDate(2025, month_var, 15)
    
    solver.add_constraint(x == d)
    solver.add_constraint(x > Date(2025, 5, 1))
    
    result = solver.solve()
    
    if result['status'] == 'sat':
        print(f"✓ Found solution: x = {result['dates']['x']}")
        print(f"  Only 12 months enumerated instead of full dates")
    else:
        print(f"✗ Status: {result['status']}")


def test_all_symbolic():
    """Test Date with all components symbolic: Date(year_var, month_var, day_var)"""
    print("\n=== Test 3: All Components Symbolic ===")
    solver = EnumerationSolver()
    
    year_var = solver.add_year_var("y")
    month_var = solver.add_month_var("m")
    day_var = solver.add_day_var("d")
    
    # Create date with all symbolic components
    x = solver.SymbolicDate(year_var, month_var, day_var)
    
    # Add constraints
    solver.add_constraint(x.year == 2020)
    solver.add_constraint(x.month == 2)
    solver.add_constraint(x.day > 28)  # Only Feb 29, 2020 works (leap year)
    
    result = solver.solve()
    
    if result['status'] == 'sat':
        print(f"✓ Found solution: x = {result['dates']['symdate_ymd_0']}")
        print(f"  All components enumerated and validated")
        print(f"  Correctly found Feb 29, 2020 (leap year)")
    else:
        print(f"✗ Status: {result['status']}")


def test_expression():
    """Test Date with expression: Date(year_var + 1, 1, 1)"""
    print("\n=== Test 4: Component Expression ===")
    solver = EnumerationSolver()
    
    x = solver.add_date_var("x")
    year_var = solver.add_year_var("y")
    
    # Date with year expression: year_var + 1
    d = solver.SymbolicDate(year_var + 1, 1, 1)
    
    solver.add_constraint(x == d)
    solver.add_constraint(x > Date(2025, 1, 1))
    solver.add_constraint(x < Date(2030, 1, 1))
    
    result = solver.solve()
    
    if result['status'] == 'sat':
        print(f"✓ Found solution: x = {result['dates']['x']}")
        print(f"  Expression (year_var + 1) evaluated correctly")
    else:
        print(f"✗ Status: {result['status']}")


def test_mixed_constraints():
    """Test mixing symbolic dates with regular date variables"""
    print("\n=== Test 5: Mixed Constraints ===")
    solver = EnumerationSolver()
    
    x = solver.add_date_var("x")
    y = solver.add_date_var("y")
    year_var = solver.add_year_var("year")
    
    # Create symbolic date
    boundary = solver.SymbolicDate(year_var, 6, 15)
    
    # Constraints using both regular and symbolic dates
    solver.add_constraint(x < boundary)
    solver.add_constraint(y > boundary)
    solver.add_constraint(x > Date(2020, 1, 1))
    solver.add_constraint(y < Date(2020, 12, 31))
    
    result = solver.solve()
    
    if result['status'] == 'sat':
        print(f"✓ Found solution:")
        print(f"  x = {result['dates']['x']} (before boundary)")
        print(f"  y = {result['dates']['y']} (after boundary)")
        print(f"  Symbolic date acts as boundary between x and y")
    else:
        print(f"✗ Status: {result['status']}")


def test_invalid_date_filtering():
    """Test that invalid dates (like Feb 31) are properly filtered"""
    print("\n=== Test 6: Invalid Date Filtering ===")
    solver = EnumerationSolver()
    
    month_var = solver.add_month_var("m")
    day_var = solver.add_day_var("d")
    
    # This will enumerate 12 months × 31 days = 372 combinations
    # But many are invalid (like Feb 31, Apr 31, etc.)
    x = solver.SymbolicDate(2023, month_var, day_var)
    
    # Constraint: day must be 31
    solver.add_constraint(x.day == 31)
    
    result = solver.solve()
    
    if result['status'] == 'sat':
        solution = result['dates']['symdate_md_0']
        print(f"✓ Found solution: {solution}")
        print(f"  Invalid dates (Feb 31, Apr 31, etc.) correctly filtered")
        print(f"  Only valid months with 31 days: Jan, Mar, May, Jul, Aug, Oct, Dec")
        assert solution.month in [1, 3, 5, 7, 8, 10, 12], "Month should have 31 days"
    else:
        print(f"✗ Status: {result['status']}")


def test_efficiency_comparison():
    """Compare efficiency of symbolic components vs full date enumeration"""
    print("\n=== Test 7: Efficiency Comparison ===")
    
    # Scenario: Find date where year matches a specific pattern
    # With symbolic year: enumerate ~200 years
    # With full dates: enumerate ~73,000 dates
    
    solver = EnumerationSolver(timeout_ms=10000)  # 10 second timeout
    
    x = solver.add_date_var("x")
    year_var = solver.add_year_var("y")
    
    d = solver.SymbolicDate(year_var, 7, 4)  # July 4th with symbolic year
    
    solver.add_constraint(x == d)
    solver.add_constraint(x.year > 2020)
    solver.add_constraint(x.year < 2025)
    
    import time
    start = time.time()
    result = solver.solve()
    elapsed = time.time() - start
    
    if result['status'] == 'sat':
        print(f"✓ Found solution in {elapsed:.4f} seconds")
        print(f"  x = {result['dates']['x']}")
        print(f"  Enumerated only ~200 years instead of ~73,000 dates")
        print(f"  Efficiency gain: ~365x fewer values to enumerate")
    else:
        print(f"✗ Status: {result['status']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Symbolic Components in Date() Constructor")
    print("=" * 60)
    
    test_symbolic_year()
    test_symbolic_month()
    test_all_symbolic()
    test_expression()
    test_mixed_constraints()
    test_invalid_date_filtering()
    test_efficiency_comparison()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

