import operator

import pytest

from datesat.core import Date
from datesat.symbolic_bitvector.alpha_beta_bv import AlphaBetaSolver
from datesat.symbolic_bitvector.alpha_beta_table_bv import AlphaBetaTableSolver
from datesat.symbolic_bitvector.naive_bv import NaiveSolver
from datesat.symbolic_bitvector.epoch_days_bv import EpochDaysSolver
from datesat.symbolic_bitvector.hybrid_bv import HybridSolver

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
@pytest.mark.naive
@pytest.mark.bitvector
def test_naive_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(NaiveSolver, a, b, op_name)
    assert sat == expect, f"Naive: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.epoch_days
@pytest.mark.bitvector
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
@pytest.mark.bitvector
def test_hybrid_date_comparisons_match_truth(op_name: str, op, a: Date, b: Date):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(HybridSolver, a, b, op_name)
    assert sat == expect, f"Hybrid: expected {expect} for {a} {op_name} {b}"


@pytest.mark.parametrize(
    "a,b",
    [pytest.param(a, b, id=f"{a}_vs_{b}") for a, b in CASES],
)
@pytest.mark.parametrize("op_name,op", OPS)
@pytest.mark.alpha_beta
@pytest.mark.bitvector
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
@pytest.mark.bitvector
def test_alpha_beta_table_date_comparisons_match_truth(
    op_name: str, op, a: Date, b: Date
):
    expect = _expect_truth(op, a, b)
    sat = _solve_compare(AlphaBetaTableSolver, a, b, op_name)
    assert sat == expect, f"AlphaBetaTable: expected {expect} for {a} {op_name} {b}"


# Tests specifically for negative epoch values (dates before 2000-03-01)
# These test cases are critical for catching signed/unsigned comparison bugs
# in epoch-based implementations (epoch_days and hybrid)
NEGATIVE_EPOCH_CONSTRAINT_CASES = [
    # Leap year Feb 29 constraint (the bug case)
    {
        "name": "leap_year_feb_29",
        "constraints": [
            ("x >= Date(2000, 2, 28)", True),
            ("x <= Date(2000, 3, 1)", True),
            ("x != Date(2000, 2, 28)", True),
            ("x != Date(2000, 3, 1)", True),
        ],
        "expected_sat": True,
        "expected_date": Date(2000, 2, 29),
    },
    # Range constraint before epoch
    {
        "name": "range_before_epoch",
        "constraints": [
            ("x >= Date(2000, 2, 27)", True),
            ("x <= Date(2000, 2, 29)", True),
        ],
        "expected_sat": True,
        "expected_date": None,  # Any date in range
    },
    # Exact constraint before epoch
    {
        "name": "exact_before_epoch",
        "constraints": [
            ("x == Date(2000, 2, 28)", True),
        ],
        "expected_sat": True,
        "expected_date": Date(2000, 2, 28),
    },
    # Comparison across epoch boundary
    {
        "name": "across_epoch_boundary",
        "constraints": [
            ("x >= Date(2000, 2, 29)", True),
            ("x <= Date(2000, 3, 2)", True),
        ],
        "expected_sat": True,
        "expected_date": None,
    },
    # Large negative epoch value
    {
        "name": "large_negative_epoch",
        "constraints": [
            ("x >= Date(1999, 3, 1)", True),
            ("x <= Date(1999, 3, 31)", True),
        ],
        "expected_sat": True,
        "expected_date": None,
    },
]


def _solve_constraints(solver_cls, constraints, constraint_code_func):
    """Solve a set of constraints and return the result."""
    s = solver_cls()
    x = s.add_date_var("x")
    
    for constraint_code, expected_sat in constraints:
        # Evaluate the constraint code in a context where 'x' and 'Date' are available
        constraint = eval(constraint_code, {"x": x, "Date": Date})
        s.add_constraint(constraint)
    
    res = s.solve()
    return res


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc["name"]) for tc in NEGATIVE_EPOCH_CONSTRAINT_CASES],
)
@pytest.mark.epoch_days
@pytest.mark.bitvector
def test_epoch_days_negative_epoch_constraints(test_case):
    """Test epoch_days implementation with negative epoch values (dates before 2000-03-01)."""
    res = _solve_constraints(EpochDaysSolver, test_case["constraints"], None)
    
    assert res["status"] == ("sat" if test_case["expected_sat"] else "unsat"), (
        f"EpochDays: Expected {test_case['expected_sat']} for {test_case['name']}, "
        f"got {res['status']}"
    )
    
    if test_case["expected_sat"] and test_case["expected_date"] is not None:
        solution_date = res["dates"]["x"]
        assert solution_date == test_case["expected_date"], (
            f"EpochDays: Expected {test_case['expected_date']} for {test_case['name']}, "
            f"got {solution_date}"
        )


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc["name"]) for tc in NEGATIVE_EPOCH_CONSTRAINT_CASES],
)
@pytest.mark.hybrid
@pytest.mark.bitvector
def test_hybrid_negative_epoch_constraints(test_case):
    """Test hybrid implementation with negative epoch values (dates before 2000-03-01)."""
    res = _solve_constraints(HybridSolver, test_case["constraints"], None)
    
    assert res["status"] == ("sat" if test_case["expected_sat"] else "unsat"), (
        f"Hybrid: Expected {test_case['expected_sat']} for {test_case['name']}, "
        f"got {res['status']}"
    )
    
    if test_case["expected_sat"] and test_case["expected_date"] is not None:
        solution_date = res["dates"]["x"]
        assert solution_date == test_case["expected_date"], (
            f"Hybrid: Expected {test_case['expected_date']} for {test_case['name']}, "
            f"got {solution_date}"
        )
