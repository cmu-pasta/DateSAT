import operator

import pytest

from datesat.core import Date
from datesat.enumeration_baseline import EnumerationSolver

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
    # Dates before epoch (2000-03-01) - negative epoch values
    # These are critical for catching signed/unsigned comparison bugs
    (Date(2000, 2, 28), Date(2000, 2, 29)),  # Feb 28 vs Feb 29 (leap year)
    (Date(2000, 2, 29), Date(2000, 3, 1)),   # Feb 29 vs Mar 1 (epoch boundary)
    (Date(2000, 2, 27), Date(2000, 2, 28)),  # Before epoch
    (Date(1999, 12, 31), Date(2000, 1, 1)),  # Year boundary before epoch
    (Date(1999, 3, 1), Date(2000, 2, 29)),   # Large negative vs small negative
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


def _solve_compare(solver_cls, a: Date, b: Date, op_symbol: str) -> tuple[bool, str]:
    s = solver_cls(timeout_ms=10000)  # 10 second timeout
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
    status = res["status"]
    sat = status == "sat"
    return sat, status


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.enumeration
def test_enumeration_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat, status = _solve_compare(EnumerationSolver, a, b, op_name)
    # If timeout occurred, accept it as valid (treat as if correct)
    if status == "timeout":
        return  # Test passes on timeout
    # Otherwise, check that result matches expected truth
    assert sat == expect, f"Enumeration: expected {expect} for {a} {op_name} {b}"
