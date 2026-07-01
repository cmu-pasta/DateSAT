"""
Test that *intermediate* DateVars introduced by date arithmetic are bounded.

These are "round-trip through out-of-range" tests:

    y = x + BIG
    z = y - BIG
    x == ANCHOR
    z == ANCHOR

- If intermediate DateVars (like `y`) are **unbounded**, this can be SAT:
  the model can set y to an out-of-range date and still satisfy z == x.

- If intermediate DateVars are **bounded** to the solver's supported range,
  this becomes UNSAT because `y` is forced out-of-range.

Note: Period has hard limits: years <= 200, months <= 2400.
"""

import pytest
from z3 import sat, unsat

# All bitvector solvers live in future_work.datesat_bounded (bounded).
from future_work.datesat_bounded.core import Date, Period
from future_work.datesat_bounded.bitvector.simple_bv import SimpleSolver
from future_work.datesat_bounded.bitvector.epoch_days_bv import EpochDaysSolver
from future_work.datesat_bounded.bitvector.hybrid_bv import HybridSolver
from future_work.datesat_bounded.bitvector.alpha_beta_bv import AlphaBetaSolver
from future_work.datesat_bounded.bitvector.alpha_beta_table_bv import AlphaBetaTableSolver


SOLVERS = [
    pytest.param(SimpleSolver, id="simple", marks=pytest.mark.simple),
    pytest.param(EpochDaysSolver, id="epoch_days", marks=pytest.mark.epoch_days),
    pytest.param(HybridSolver, id="hybrid", marks=pytest.mark.hybrid),
    pytest.param(AlphaBetaSolver, id="alpha_beta", marks=pytest.mark.alpha_beta),
    pytest.param(AlphaBetaTableSolver, id="alpha_beta_table", marks=pytest.mark.alpha_beta_table),
]

ANCHOR = Date(2000, 1, 15)  # avoid EOM/leap-day corner cases
MAX_YEARS = 200             # Period constraint: |years| <= 200
MAX_MONTHS = 2400           # Period constraint: |months| <= 2400 (200 years)


@pytest.mark.parametrize("solver_cls", SOLVERS)
@pytest.mark.bitvector
def test_round_trip_small_period_is_sat(solver_cls):
    """Sanity: small round-trip should always be SAT."""
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(1, 0, 0)
    z = y - Period(1, 0, 0)

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    assert solver.check() == sat


@pytest.mark.parametrize("solver_cls", SOLVERS)
@pytest.mark.bitvector
def test_round_trip_via_out_of_range_intermediate_years_future_is_unsat(solver_cls):
    """
    Shift far into the future (within Period limits), then shift back.
    Should be UNSAT iff the intermediate `y` is bounded.
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(MAX_YEARS, 0, 0)   # intermediate (should be bounded!)
    z = y - Period(MAX_YEARS, 0, 0)   # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == unsat, (
        f"{solver_cls.__name__} returned {res}. "
        "This usually means the intermediate DateVar created by `x + Period(...)` is still unbounded."
    )


@pytest.mark.parametrize("solver_cls", SOLVERS)
@pytest.mark.bitvector
def test_round_trip_via_out_of_range_intermediate_years_past_is_unsat(solver_cls):
    """
    Shift far into the past (within Period limits), then shift back.
    Should be UNSAT iff the intermediate `y` is bounded.
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x - Period(MAX_YEARS, 0, 0)   # intermediate (should be bounded!)
    z = y + Period(MAX_YEARS, 0, 0)   # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == unsat, (
        f"{solver_cls.__name__} returned {res}. "
        "This usually means the intermediate DateVar created by `x - Period(...)` is still unbounded."
    )


@pytest.mark.parametrize("solver_cls", SOLVERS)
@pytest.mark.bitvector
def test_round_trip_via_out_of_range_intermediate_months_future_is_unsat(solver_cls):
    """
    Same idea, but using months (to catch implementations that treat years specially).
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(0, MAX_MONTHS, 0)  # intermediate (should be bounded!)
    z = y - Period(0, MAX_MONTHS, 0)  # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == unsat, (
        f"{solver_cls.__name__} returned {res}. "
        "This usually means the intermediate DateVar created by `x + Period(...)` is still unbounded."
    )


@pytest.mark.parametrize("solver_cls", SOLVERS)
@pytest.mark.bitvector
def test_round_trip_via_out_of_range_intermediate_months_past_is_unsat(solver_cls):
    """Months version (past shift)."""
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x - Period(0, MAX_MONTHS, 0)  # intermediate (should be bounded!)
    z = y + Period(0, MAX_MONTHS, 0)  # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == unsat, (
        f"{solver_cls.__name__} returned {res}. "
        "This usually means the intermediate DateVar created by `x - Period(...)` is still unbounded."
    )
