"""
Dates are unbounded by default: a model may contain years below 1 or above 9999,
and Date + Period results are computed exactly there. With python_bounds=True every
date, including every intermediate Date + Period result and every concrete Date in
the constraints, is bounded to Python's datetime.date range, years 1..9999.
"""

import random

import pytest

import datesat
from datesat import DateSATBuilder
from datesat.core import Date, Period
from datesat.symbolic_int.alpha_beta_int import AlphaBetaSolver
from datesat.symbolic_int.epoch_days_int import EpochDaysSolver
from datesat.symbolic_int.hybrid_init_epoch_int import HybridInitEpochSolver
from datesat.symbolic_int.hybrid_init_ymd_int import HybridInitYmdSolver
from datesat.symbolic_int.simple_int import SimpleSolver

SOLVERS = [
    pytest.param(SimpleSolver, id="simple", marks=pytest.mark.simple),
    pytest.param(EpochDaysSolver, id="epoch_days", marks=pytest.mark.epoch_days),
    pytest.param(HybridInitEpochSolver, id="hybrid_init_epoch", marks=pytest.mark.hybrid_init_epoch),
    pytest.param(HybridInitYmdSolver, id="hybrid_init_ymd", marks=pytest.mark.hybrid_init_ymd),
    pytest.param(AlphaBetaSolver, id="alpha_beta", marks=pytest.mark.alpha_beta),
]

APPROACHES = [
    pytest.param("simple", marks=pytest.mark.simple),
    pytest.param("epoch_days", marks=pytest.mark.epoch_days),
    pytest.param("hybrid_init_epoch", marks=pytest.mark.hybrid_init_epoch),
    pytest.param("hybrid_init_ymd", marks=pytest.mark.hybrid_init_ymd),
    pytest.param("alpha_beta", marks=pytest.mark.alpha_beta),
]

pytestmark = pytest.mark.integer


# ── Solver classes ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_default_allows_years_beyond_9999(solver_cls):
    s = solver_cls()
    x = s.add_date_var("x")
    s.add_constraint(x > Date(9999, 12, 31))
    s.add_constraint(x < Date(10000, 1, 3))
    r = s.solve()
    assert r["status"] == "sat"
    assert r["dates"]["x"] in (Date(10000, 1, 1), Date(10000, 1, 2))


@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_default_allows_years_before_1(solver_cls):
    s = solver_cls()
    x = s.add_date_var("x")
    s.add_constraint(x < Date(1, 1, 1))
    s.add_constraint(x > Date(0, 12, 29))
    r = s.solve()
    assert r["status"] == "sat"
    assert r["dates"]["x"] in (Date(0, 12, 30), Date(0, 12, 31))


@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_python_bounds_rejects_years_outside_1_9999(solver_cls):
    s = solver_cls(python_bounds=True)
    x = s.add_date_var("x")
    s.add_constraint(x > Date(9999, 12, 31))
    assert s.solve()["status"] == "unsat"

    s = solver_cls(python_bounds=True)
    x = s.add_date_var("x")
    s.add_constraint(x < Date(1, 1, 1))
    assert s.solve()["status"] == "unsat"


@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_python_bounds_keeps_the_ends_of_the_range(solver_cls):
    s = solver_cls(python_bounds=True)
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x >= Date(9999, 12, 31))
    s.add_constraint(y <= Date(1, 1, 1))
    r = s.solve()
    assert r["status"] == "sat"
    assert r["dates"]["x"] == Date(9999, 12, 31)
    assert r["dates"]["y"] == Date(1, 1, 1)


@pytest.mark.parametrize("python_bounds, expected", [(False, "sat"), (True, "unsat")])
@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_intermediate_result_beyond_9999(solver_cls, python_bounds, expected):
    """y = x + 1 year is 10000-06-01: fine by default, bounded out by python_bounds."""
    s = solver_cls(python_bounds=python_bounds)
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x == Date(9999, 6, 1))
    s.add_constraint(y == x + Period(1, 0, 0))
    r = s.solve()
    assert r["status"] == expected
    if expected == "sat":
        assert r["dates"]["y"] == Date(10000, 6, 1)


@pytest.mark.parametrize("python_bounds, expected", [(False, "sat"), (True, "unsat")])
@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_round_trip_through_out_of_range_intermediate(solver_cls, python_bounds, expected):
    """z = (x + 300 years) - 300 years == x with x in 9900: the unnamed intermediate
    lies beyond 9999, so python_bounds makes it unsat even though z is in range."""
    s = solver_cls(python_bounds=python_bounds)
    x = s.add_date_var("x")
    z = s.add_date_var("z")
    s.add_constraint(x == Date(9900, 1, 15))
    s.add_constraint(z == (x + Period(300, 0, 0)) - Period(300, 0, 0))
    s.add_constraint(z == x)
    assert s.solve()["status"] == expected


@pytest.mark.parametrize("python_bounds, expected", [(False, "sat"), (True, "unsat")])
@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_intermediate_result_before_year_1(solver_cls, python_bounds, expected):
    s = solver_cls(python_bounds=python_bounds)
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x == Date(5, 1, 1))
    s.add_constraint(y == x - Period(10, 0, 0))
    r = s.solve()
    assert r["status"] == expected
    if expected == "sat":
        assert r["dates"]["y"] == Date(-5, 1, 1)


@pytest.mark.parametrize("solver_cls", SOLVERS)
def test_unbounded_arithmetic_matches_concrete_date_far_outside_python_range(solver_cls):
    """Symbolic x + P agrees with core.Date arithmetic for years well outside 1..9999."""
    rng = random.Random(hash(solver_cls.__name__) & 0xFFFF)
    cases = []
    for _ in range(12):
        year = rng.choice([rng.randint(-3000, 0), rng.randint(10000, 20000)])
        month = rng.randint(1, 12)
        base = Date(year, month, rng.randint(1, 28))
        if rng.random() < 0.3:  # end-of-month dates exercise the clamp
            base = Date(year, month, 1) + Period(0, 1, -1)
        cases.append((base, Period(rng.randint(-20, 20), rng.randint(-30, 30), rng.randint(-800, 800))))
    cases += [
        (Date(0, 2, 29), Period(1, 0, 0)),
        (Date(-1, 1, 31), Period(0, 1, 1)),
        (Date(9999, 12, 31), Period(0, 0, 1)),
        (Date(1, 1, 1), Period(0, 0, -1)),
        (Date(10000, 1, 31), Period(0, 1, 0)),
    ]
    for base, period in cases:
        s = solver_cls()
        x = s.add_date_var("x")
        y = s.add_date_var("y")
        s.add_constraint(x == base)
        s.add_constraint(y == x + period)
        r = s.solve()
        assert r["status"] == "sat", (base, period)
        assert r["dates"]["y"] == base + period, (base, period, r["dates"]["y"])


# ── datesat.solve / DateSATBuilder ──────────────────────────────────────────

@pytest.mark.parametrize("approach", APPROACHES)
def test_solve_default_is_unbounded(approach):
    r = datesat.solve(
        {"declarations": ["x: date", "y: date"],
         "constraints": ["x == Date(9999, 6, 1)", "y == x + Period(1, 0, 0)"]},
        approach=approach, verbose=False)
    assert r["status"] == "sat"
    assert r["dates"]["y"] == Date(10000, 6, 1)
    assert r["python_bounds"] is False
    with pytest.raises(ValueError):
        r["dates"]["y"].to_python_date()


@pytest.mark.parametrize("approach", APPROACHES)
def test_solve_python_bounds_bounds_intermediates(approach):
    r = datesat.solve(
        {"declarations": ["x: date", "y: date"],
         "constraints": ["x == Date(9999, 6, 1)", "y == x + Period(1, 0, 0)"]},
        approach=approach, verbose=False, python_bounds=True)
    assert r["status"] == "unsat"
    assert r["python_bounds"] is True


@pytest.mark.parametrize("approach", APPROACHES)
def test_solve_python_bounds_concrete_dates_take_the_datetime_path(approach):
    # A concrete literal outside the range: fine by default, rejected by datetime
    # under python_bounds (as the original implementation did).
    problem = {"declarations": ["x: date"], "constraints": ["x > Date(10000, 1, 1)"]}
    assert datesat.solve(problem, approach=approach, verbose=False)["status"] == "sat"
    with pytest.raises(ValueError, match="Invalid date"):
        datesat.solve(problem, approach=approach, verbose=False, python_bounds=True)
    # A concrete Date + Period whose result leaves the range.
    problem = {"declarations": ["x: date"],
               "constraints": ["x >= Date(9999, 12, 1) + Period(0, 0, 60)"]}
    r = datesat.solve(problem, approach=approach, verbose=False)
    assert r["status"] == "sat" and r["dates"]["x"] >= Date(10000, 1, 30)
    with pytest.raises((ValueError, OverflowError)):
        datesat.solve(problem, approach=approach, verbose=False, python_bounds=True)


@pytest.mark.parametrize("approach", APPROACHES)
def test_solve_python_bounds_returns_bounded_dates(approach):
    r = datesat.solve(
        {"declarations": ["x: date", "y: date"],
         "constraints": ["x == Date(2024, 1, 31)", "y == x + Period(0, 1, 0)"]},
        approach=approach, verbose=False, python_bounds=True)
    assert r["status"] == "sat"
    assert all(d.bounded for d in r["dates"].values())
    assert r["dates"]["y"] == Date(2024, 2, 29)
    r = datesat.solve(
        {"declarations": ["x: date"], "constraints": ["x == Date(2024, 1, 31)"]},
        approach=approach, verbose=False)
    assert not r["dates"]["x"].bounded


@pytest.mark.parametrize("approach", APPROACHES)
def test_solve_python_bounds_in_range_problem_still_sat(approach):
    r = datesat.solve(
        {"declarations": ["x: date", "y: date"],
         "constraints": ["x >= Date(2024, 1, 31)", "x < Date(2024, 2, 1)", "y == x + Period(0, 1, 0)"]},
        approach=approach, verbose=False, python_bounds=True)
    assert r["status"] == "sat"
    assert r["dates"] == {"x": Date(2024, 1, 31), "y": Date(2024, 2, 29)}


def test_builder_python_bounds():
    b = DateSATBuilder(approach="simple", python_bounds=True)
    assert b.python_bounds and b.solver.python_bounds
    assert not DateSATBuilder(approach="simple").solver.python_bounds
