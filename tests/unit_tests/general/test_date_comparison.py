import operator

import pytest

from datesmt.core import Date
from datesmt.symbolic_alpha_beta import AlphaBetaSolver
from datesmt.symbolic_alpha_beta_table import AlphaBetaTableSolver
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_epoch_days import EpochDaysSolver
from datesmt.symbolic_hybrid import HybridDateSolver

# We cover equality, less/greater, boundary conditions, leap cases, and month ends.
CASES = [
    # Equal dates
    (Date(2020, 6, 15), Date(2020, 6, 15)),
    (Date(2000, 2, 29), Date(2000, 2, 29)),  # leap day
    # Same Y/M, different days
    (Date(2020, 6, 14), Date(2020, 6, 15)),
    (Date(2020, 6, 16), Date(2020, 6, 15)),
    # Same Y, different months
    (Date(2020, 5, 31), Date(2020, 6, 1)),
    (Date(2020, 7, 1), Date(2020, 6, 30)),
    # Different years
    (Date(2019, 12, 31), Date(2020, 1, 1)),
    (Date(2021, 1, 1), Date(2020, 12, 31)),
    # Month ends and varying month lengths
    (Date(2020, 1, 31), Date(2020, 2, 1)),
    (Date(2020, 2, 29), Date(2020, 3, 1)),  # leap Feb
    (Date(2021, 2, 28), Date(2021, 3, 1)),  # non-leap Feb
]


OPS = [
    ("==", operator.eq),
    ("!=", operator.ne),
    ("<", operator.lt),
    ("<=", operator.le),
    (">", operator.gt),
    (">=", operator.ge),
]


def _expect_truth(op, a: Date, b: Date) -> bool:
    ta = (a.year, a.month, a.day)
    tb = (b.year, b.month, b.day)
    return op(ta, tb)


def _solve_compare(solver_cls, a: Date, b: Date, op_symbol: str) -> bool:
    s = solver_cls()
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    # bind symbolic vars to concrete dates
    s.add_constraint(x == a)
    s.add_constraint(y == b)

    # Build comparison according to symbol
    if op_symbol == "==":
        s.add_constraint(x == y)
    elif op_symbol == "!=":
        s.add_constraint(x != y)
    elif op_symbol == "<":
        s.add_constraint(x < y)
    elif op_symbol == "<=":
        s.add_constraint(x <= y)
    elif op_symbol == ">":
        s.add_constraint(x > y)
    elif op_symbol == ">=":
        s.add_constraint(x >= y)
    else:
        raise ValueError(f"unknown op {op_symbol}")

    res = s.solve()
    return res["status"] == "sat"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.baseline
def test_baseline_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(BaselineSolver, a, b, op_name)
    assert sat == expect, f"Baseline: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.epoch_days
def test_epoch_days_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(EpochDaysSolver, a, b, op_name)
    assert sat == expect, f"EpochDays: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.hybrid
def test_hybrid_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(HybridDateSolver, a, b, op_name)
    assert sat == expect, f"Hybrid: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.alpha_beta
def test_alpha_beta_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(AlphaBetaSolver, a, b, op_name)
    assert sat == expect, f"AlphaBeta: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.alpha_beta_table
def test_alpha_beta_table_date_comparisons_match_truth(
    op_name: str, op, a: Date, b: Date
):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(AlphaBetaTableSolver, a, b, op_name)
    assert sat == expect, f"AlphaBetaTable: expected {expect} for {a} {op_name} {b}"
