"""
Test that *intermediate* DateVars introduced by date arithmetic behave correctly
under the solver's bounding policy.

These are "round-trip through out-of-range" tests:

    y = x + BIG
    z = y - BIG
    x == ANCHOR
    z == ANCHOR

- If intermediate DateVars (like `y`) are **unbounded**, this is SAT:
  the intermediate can hold an out-of-range date and still satisfy z == x.

- If intermediate DateVars are **bounded** to the solver's supported range,
  this is UNSAT because `y` is forced out-of-range.

Current policy (as of the range-bound removal):
  - Solvers in `datesat.symbolic_int` do NOT bound date variables to any year
    range; only well-formedness (valid calendar date) is enforced. Round-trip
    through out-of-range is therefore expected SAT for these.
  - `AlphaBetaTableSolver` in `future_work.datesat_bounded` remains bounded to
    [1900-03-01, 2100-02-28] and is expected UNSAT.

Note: Period has hard limits: years <= 200, months <= 2400.
"""

import pytest
from z3 import sat, unsat

from datesat.core import Date, Period
from datesat.symbolic_int.simple_int import SimpleSolver
from datesat.symbolic_int.epoch_days_int import EpochDaysSolver
from datesat.symbolic_int.hybrid_epoch_int import HybridEpochSolver
from datesat.symbolic_int.hybrid_ymd_int import HybridYmdSolver
from datesat.symbolic_int.alpha_beta_int import AlphaBetaSolver
from future_work.datesat_bounded.alpha_beta_table_int import AlphaBetaTableSolver


# (solver_cls, is_bounded) — is_bounded controls the expected round-trip outcome.
SOLVERS = [
    pytest.param(SimpleSolver, False, id="simple", marks=pytest.mark.simple),
    pytest.param(EpochDaysSolver, False, id="epoch_days", marks=pytest.mark.epoch_days),
    pytest.param(HybridEpochSolver, False, id="hybrid_epoch", marks=pytest.mark.hybrid_epoch),
    pytest.param(HybridYmdSolver, False, id="hybrid_ymd", marks=pytest.mark.hybrid_ymd),
    pytest.param(AlphaBetaSolver, False, id="alpha_beta", marks=pytest.mark.alpha_beta),
    pytest.param(AlphaBetaTableSolver, True, id="alpha_beta_table", marks=pytest.mark.alpha_beta_table),
]

# Solver list without the bounding flag, for tests where all solvers share the same expected outcome.
SOLVERS_ONLY = [
    pytest.param(SimpleSolver, id="simple", marks=pytest.mark.simple),
    pytest.param(EpochDaysSolver, id="epoch_days", marks=pytest.mark.epoch_days),
    pytest.param(HybridEpochSolver, id="hybrid_epoch", marks=pytest.mark.hybrid_epoch),
    pytest.param(HybridYmdSolver, id="hybrid_ymd", marks=pytest.mark.hybrid_ymd),
    pytest.param(AlphaBetaSolver, id="alpha_beta", marks=pytest.mark.alpha_beta),
    pytest.param(AlphaBetaTableSolver, id="alpha_beta_table", marks=pytest.mark.alpha_beta_table),
]

ANCHOR = Date(2000, 1, 15)  # avoid EOM/leap-day corner cases
MAX_YEARS = 200             # Period constraint: |years| <= 200
MAX_MONTHS = 2400           # Period constraint: |months| <= 2400 (200 years)


def _expected(is_bounded: bool):
    return unsat if is_bounded else sat


def _explanation(solver_cls, res, is_bounded: bool) -> str:
    if is_bounded:
        return (
            f"{solver_cls.__name__} returned {res}. "
            "This bounded solver should force the intermediate DateVar out-of-range and be UNSAT."
        )
    return (
        f"{solver_cls.__name__} returned {res}. "
        "Unbounded solvers should let the intermediate DateVar hold an out-of-range date "
        "and satisfy the round-trip (expected SAT)."
    )


@pytest.mark.parametrize("solver_cls", SOLVERS_ONLY)
@pytest.mark.integer
def test_round_trip_small_period_is_sat(solver_cls):
    """Sanity: small round-trip should always be SAT."""
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(1, 0, 0)
    z = y - Period(1, 0, 0)

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    assert solver.check() == sat


@pytest.mark.parametrize("solver_cls,is_bounded", SOLVERS)
@pytest.mark.integer
def test_round_trip_via_out_of_range_intermediate_years_future(solver_cls, is_bounded):
    """
    Shift far into the future (within Period limits), then shift back.
    UNSAT for bounded solvers, SAT for unbounded solvers.
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(MAX_YEARS, 0, 0)   # intermediate (bounded solvers reject this)
    z = y - Period(MAX_YEARS, 0, 0)   # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == _expected(is_bounded), _explanation(solver_cls, res, is_bounded)


@pytest.mark.parametrize("solver_cls,is_bounded", SOLVERS)
@pytest.mark.integer
def test_round_trip_via_out_of_range_intermediate_years_past(solver_cls, is_bounded):
    """
    Shift far into the past (within Period limits), then shift back.
    UNSAT for bounded solvers, SAT for unbounded solvers.
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x - Period(MAX_YEARS, 0, 0)   # intermediate (bounded solvers reject this)
    z = y + Period(MAX_YEARS, 0, 0)   # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == _expected(is_bounded), _explanation(solver_cls, res, is_bounded)


@pytest.mark.parametrize("solver_cls,is_bounded", SOLVERS)
@pytest.mark.integer
def test_round_trip_via_out_of_range_intermediate_months_future(solver_cls, is_bounded):
    """
    Same idea, but using months (to catch implementations that treat years specially).
    UNSAT for bounded solvers, SAT for unbounded solvers.
    """
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x + Period(0, MAX_MONTHS, 0)  # intermediate (bounded solvers reject this)
    z = y - Period(0, MAX_MONTHS, 0)  # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == _expected(is_bounded), _explanation(solver_cls, res, is_bounded)


@pytest.mark.parametrize("solver_cls,is_bounded", SOLVERS)
@pytest.mark.integer
def test_round_trip_via_out_of_range_intermediate_months_past(solver_cls, is_bounded):
    """Months version (past shift). UNSAT for bounded solvers, SAT for unbounded solvers."""
    solver = solver_cls()
    x = solver.add_date_var("x")

    y = x - Period(0, MAX_MONTHS, 0)  # intermediate (bounded solvers reject this)
    z = y + Period(0, MAX_MONTHS, 0)  # back to anchor

    solver.add_constraint(x == ANCHOR)
    solver.add_constraint(z == ANCHOR)

    res = solver.check()
    assert res == _expected(is_bounded), _explanation(solver_cls, res, is_bounded)
