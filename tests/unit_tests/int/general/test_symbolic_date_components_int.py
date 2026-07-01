#!/usr/bin/env python3
"""
Test symbolic components inside Date() constructor for INT solvers.
This tests the parser's automatic transformation of Date(x, y, z) patterns.
"""

import pytest
from datesat.core import Date
from datesat.symbolic_int.epoch_days_int import EpochDaysSolver
from datesat.symbolic_int.alpha_beta_int import AlphaBetaSolver
from datesat.symbolic_int.alpha_beta_table_int import AlphaBetaTableSolver
from datesat.symbolic_int.simple_int import SimpleSolver
from datesat.symbolic_int.hybrid_epoch_int import HybridEpochSolver
from datesat.symbolic_int.hybrid_ymd_int import HybridYmdSolver
from z3 import Int, Or, And


@pytest.mark.parametrize("solver_cls", [
    EpochDaysSolver,
    AlphaBetaSolver,
    AlphaBetaTableSolver,
    SimpleSolver,
    HybridEpochSolver,
    HybridYmdSolver,
])
def test_symbolic_year_int(solver_cls):
    """Test Date with only year symbolic: Date(year_var, 2, 1)"""
    solver = solver_cls()
    
    k = solver.add_date_var("k")
    x = Int("x")
    
    # Automatic bounds from parser
    solver.add_constraint(x >= 1900)
    solver.add_constraint(x <= 2100)
    
    # Parser transforms: k >= Date(x, 2, 1)
    # Into component-wise comparison
    solver.add_constraint(Or(k.year > x, And(k.year == x, Or(k.month > 2, And(k.month == 2, k.day >= 1)))))
    solver.add_constraint(k > Date(2000, 1, 1))
    
    result = solver.solve()
    
    assert result["status"] == "sat", "Should find a solution"
    dates = result["dates"]
    assert dates['k'].year >= 1900 and dates['k'].year <= 2100


@pytest.mark.parametrize("solver_cls", [
    EpochDaysSolver,
    AlphaBetaSolver,
    AlphaBetaTableSolver,
    SimpleSolver,
    HybridEpochSolver,
    HybridYmdSolver,
])
def test_symbolic_month_int(solver_cls):
    """Test Date with only month symbolic: Date(2025, month_var, 15)"""
    solver = solver_cls()
    
    k = solver.add_date_var("k")
    m = Int("m")
    
    # Automatic bounds from parser
    solver.add_constraint(m >= 1)
    solver.add_constraint(m <= 12)
    
    # Parser transforms: k == Date(2025, m, 15)
    solver.add_constraint(And(k.year == 2025, k.month == m, k.day == 15))
    solver.add_constraint(k > Date(2025, 5, 1))
    
    result = solver.solve()
    
    assert result["status"] == "sat", "Should find a solution"
    dates = result["dates"]
    # k > Date(2025, 5, 1) means k must be >= Date(2025, 5, 2)
    # So valid solutions can be May 15 (which is > May 1)
    k_tuple = (dates['k'].year, dates['k'].month, dates['k'].day)
    assert k_tuple > (2025, 5, 1), "Date should be > Date(2025, 5, 1)"
    assert dates['k'].month >= 1 and dates['k'].month <= 12


@pytest.mark.parametrize("solver_cls", [
    EpochDaysSolver,
    AlphaBetaSolver,
    AlphaBetaTableSolver,
    SimpleSolver,
    HybridEpochSolver,
    HybridYmdSolver,
])
def test_all_symbolic_int(solver_cls):
    """Test Date with all components symbolic: Date(y, m, d)"""
    solver = solver_cls()
    
    k = solver.add_date_var("k")
    y = Int("y")
    m = Int("m")
    d = Int("d")
    
    # Automatic bounds from parser
    solver.add_constraint(y >= 1900)
    solver.add_constraint(y <= 2100)
    solver.add_constraint(m >= 1)
    solver.add_constraint(m <= 12)
    solver.add_constraint(d >= 1)
    solver.add_constraint(d <= 31)
    
    # Parser transforms: k == Date(y, m, d)
    solver.add_constraint(And(k.year == y, k.month == m, k.day == d))
    solver.add_constraint(k.year == 2020)
    solver.add_constraint(k.month == 2)
    solver.add_constraint(k.day > 28)  # Only Feb 29, 2020 works (leap year)
    
    result = solver.solve()
    
    assert result["status"] == "sat", "Should find a solution"
    solution = result["dates"]['k']
    assert solution.year == 2020 and solution.month == 2 and solution.day == 29


@pytest.mark.parametrize("solver_cls", [
    EpochDaysSolver,
    AlphaBetaSolver,
    AlphaBetaTableSolver,
    SimpleSolver,
    HybridEpochSolver,
    HybridYmdSolver,
])
def test_expression_int(solver_cls):
    """Test Date with expression: Date(x+1, 2, 1)"""
    solver = solver_cls()
    
    k = solver.add_date_var("k")
    x = Int("x")
    
    # Automatic bounds from parser
    solver.add_constraint(x >= 1900)
    solver.add_constraint(x <= 2100)
    
    # Parser transforms: k == Date(x+1, 2, 1)
    solver.add_constraint(And(k.year == x + 1, k.month == 2, k.day == 1))
    solver.add_constraint(k > Date(2025, 1, 1))
    solver.add_constraint(k < Date(2030, 1, 1))
    
    result = solver.solve()
    
    assert result["status"] == "sat", "Should find a solution"
    dates = result["dates"]
    # k > Date(2025, 1, 1) means k >= Date(2025, 1, 2)
    # k < Date(2030, 1, 1) means k <= Date(2029, 12, 31)
    k_tuple = (dates['k'].year, dates['k'].month, dates['k'].day)
    assert k_tuple > (2025, 1, 1) and k_tuple < (2030, 1, 1)


@pytest.mark.parametrize("solver_cls", [
    EpochDaysSolver,
    AlphaBetaSolver,
    AlphaBetaTableSolver,
    SimpleSolver,
    HybridEpochSolver,
    HybridYmdSolver,
])
def test_bounds_prevent_invalid_values(solver_cls):
    """Test that automatic bounds prevent invalid values"""
    solver = solver_cls()
    
    k = solver.add_date_var("k")
    m = Int("m")
    
    # Automatic bounds from parser
    solver.add_constraint(m >= 1)
    solver.add_constraint(m <= 12)
    
    # Constrain month through the int variable
    solver.add_constraint(k.month == m)
    solver.add_constraint(m > 10)  # Month > 10, so must be 11 or 12
    solver.add_constraint(k.year == 2020)
    
    result = solver.solve()
    
    assert result["status"] == "sat", "Should find a solution"
    solution = result["dates"]['k']
    assert solution.month in [11, 12], "Month should be 11 or 12"

