from datetime import date as pydate

import pytest

from datesat.core import Date, Period
from datesat.symbolic_int.alpha_beta_int import AlphaBetaSolver
from future_work.datesat_bounded.alpha_beta_table_int import AlphaBetaTableSolver
from datesat.symbolic_int.simple_int import SimpleSolver
from datesat.symbolic_int.epoch_days_int import EpochDaysSolver
from datesat.symbolic_int.hybrid_epoch_int import HybridEpochSolver
from datesat.symbolic_int.hybrid_ymd_int import HybridYmdSolver


def _apply_sequence_python(base: Date, seq: list[Period]) -> Date:
    d = pydate(base.year, base.month, base.day)
    y, m, day = d.year, d.month, d.day
    for p in seq:
        # Year, then month, then day semantics
        y += p.years
        m += p.months
        # normalize months into year range
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
        # clamp day if overflow in target month
        from calendar import monthrange

        dim = monthrange(y, m)[1]
        day = min(day, dim)
        # then add days as date arithmetic
        d = pydate(y, m, day)
        d = d.fromordinal(d.toordinal() + p.days)
        y, m, day = d.year, d.month, d.day
    return Date(y, m, day)


def _solve_with_solver(solver_cls, base: Date, seq: list[Period]):
    s = solver_cls()
    x = s.add_date_var("x")
    s.add_constraint(x == base)
    cur = x
    for i, p in enumerate(seq):
        t = s.add_date_var(f"t{i}")
        s.add_constraint(t == cur + p)
        cur = t
    y = s.add_date_var("y")
    s.add_constraint(y == cur)
    return s.solve()

def _solve_with_solver_sub(solver_cls, base: Date, seq: list[Period]):
    # Implement each step via subtraction of the negated period
    s = solver_cls()
    x = s.add_date_var("x")
    s.add_constraint(x == base)
    cur = x
    for i, p in enumerate(seq):
        t = s.add_date_var(f"t{i}")
        neg = Period(-p.years, -p.months, -p.days)
        s.add_constraint(t == cur - neg)
        cur = t
    y = s.add_date_var("y")
    s.add_constraint(y == cur)
    return s.solve()


MULTI_OP_CASES = [
    # Mixed month/day steps around month-ends
    (Date(2023, 1, 30), [Period(0, 1, 0), Period(0, 1, 0)]),  # -> 2023-03-28
    (Date(2024, 1, 31), [Period(0, 1, 0), Period(0, 1, 0)]),  # leap-year Feb handling
    (Date(2023, 2, 28), [Period(0, 0, 1), Period(0, 1, 0)]),
    (Date(2020, 2, 29), [Period(1, 0, 0), Period(0, 1, 0)]),
    (Date(2023, 12, 31), [Period(0, 1, 0), Period(0, 0, 1)]),
    # Longer chains
    (Date(2023, 3, 31), [Period(0, 1, 0), Period(0, 1, 0), Period(0, 1, 0)]),
    (Date(2020, 1, 31), [Period(0, 1, 0), Period(0, 1, 0), Period(0, 1, 0)]),
    (Date(2021, 1, 15), [Period(1, 0, 0), Period(0, 2, 0), Period(0, 0, 17)]),
    # Negative steps
    (Date(2023, 3, 1), [Period(0, -1, 0), Period(0, 0, -1)]),
    (Date(2024, 3, 1), [Period(-1, 0, 0), Period(0, -1, 0), Period(0, 0, -1)]),
]


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.simple
@pytest.mark.integer
def test_stepwise_multi_op_baseline_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(SimpleSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.epoch_days
@pytest.mark.integer
def test_stepwise_multi_op_epoch_days_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(EpochDaysSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize(
    "solver_cls",
    [
        pytest.param(HybridEpochSolver, id="hybrid_epoch", marks=pytest.mark.hybrid_epoch),
        pytest.param(HybridYmdSolver, id="hybrid_ymd", marks=pytest.mark.hybrid_ymd),
    ],
)
@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.integer
def test_stepwise_multi_op_hybrid_matches_python(solver_cls, base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(solver_cls, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_stepwise_multi_op_alpha_beta_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(AlphaBetaSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta_table
@pytest.mark.integer
def test_stepwise_multi_op_alpha_beta_table_matches_python(
    base: Date, seq: list[Period]
):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(AlphaBetaTableSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected




# sub sequence: implement each addition via subtracting the negated period.
# If any intermediate step would go out of domain, the solver should report UNSAT.
@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.simple
@pytest.mark.integer
def test_stepwise_multi_op_sub_baseline_matches_python(base: Date, seq: list[Period]):
    res = _solve_with_solver_sub(SimpleSolver, base, seq)
    if res["status"] == "unsat":
        return
    expected = _apply_sequence_python(base, seq)
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.epoch_days
@pytest.mark.integer
def test_stepwise_multi_op_sub_epoch_days_matches_python(base: Date, seq: list[Period]):
    res = _solve_with_solver_sub(EpochDaysSolver, base, seq)
    if res["status"] == "unsat":
        return
    expected = _apply_sequence_python(base, seq)
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize(
    "solver_cls",
    [
        pytest.param(HybridEpochSolver, id="hybrid_epoch", marks=pytest.mark.hybrid_epoch),
        pytest.param(HybridYmdSolver, id="hybrid_ymd", marks=pytest.mark.hybrid_ymd),
    ],
)
@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.integer
def test_stepwise_multi_op_sub_hybrid_matches_python(solver_cls, base: Date, seq: list[Period]):
    res = _solve_with_solver_sub(solver_cls, base, seq)
    if res["status"] == "unsat":
        return
    expected = _apply_sequence_python(base, seq)
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_stepwise_multi_op_sub_alpha_beta_matches_python(base: Date, seq: list[Period]):
    res = _solve_with_solver_sub(AlphaBetaSolver, base, seq)
    if res["status"] == "unsat":
        return
    expected = _apply_sequence_python(base, seq)
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta_table
@pytest.mark.integer
def test_stepwise_multi_op_sub_alpha_beta_table_matches_python(
    base: Date, seq: list[Period]
):
    res = _solve_with_solver_sub(AlphaBetaTableSolver, base, seq)
    if res["status"] == "unsat":
        return
    expected = _apply_sequence_python(base, seq)
    assert res["dates"]["y"] == expected
