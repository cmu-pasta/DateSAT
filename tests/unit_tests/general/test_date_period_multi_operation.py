from datetime import date as pydate

import pytest

from datesmt.core import Date, Period
from datesmt.symbolic_alpha_beta import AlphaBetaSolver
from datesmt.symbolic_alpha_beta_table import AlphaBetaTableSolver
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_epoch_days import EpochDaysSolver
from datesmt.symbolic_hybrid import HybridDateSolver


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
@pytest.mark.baseline
def test_stepwise_multi_op_baseline_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(BaselineSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.epoch_days
def test_stepwise_multi_op_epoch_days_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(EpochDaysSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.hybrid
def test_stepwise_multi_op_hybrid_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(HybridDateSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta
def test_stepwise_multi_op_alpha_beta_matches_python(base: Date, seq: list[Period]):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(AlphaBetaSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected


@pytest.mark.parametrize("base,seq", MULTI_OP_CASES)
@pytest.mark.alpha_beta_table
def test_stepwise_multi_op_alpha_beta_table_matches_python(
    base: Date, seq: list[Period]
):
    expected = _apply_sequence_python(base, seq)
    res = _solve_with_solver(AlphaBetaTableSolver, base, seq)
    assert res["status"] == "sat"
    assert res["dates"]["y"] == expected
