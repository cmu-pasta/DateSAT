from itertools import permutations

import pytest
from dateutil.relativedelta import relativedelta

from datesmt.core import Date, Period
from datesmt.symbolic_alpha_beta import AlphaBetaSolver
from datesmt.symbolic_alpha_beta_table import AlphaBetaTableSolver
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_epoch_days import EpochDaysSolver
from datesmt.symbolic_hybrid import HybridDateSolver

# Local copy of canonical test cases (migrated from test_date_period_operation.py)


def get_period_arithmetic_test_cases():
    return [
        (Date(2020, 6, 15), Period(1, 2, 3)),
        (Date(2020, 6, 15), Period(2, 6, 10)),
        (Date(2020, 6, 15), Period(-1, -2, -3)),
        (Date(2020, 2, 29), Period(1, 0, 0)),
        (Date(2020, 1, 31), Period(0, 1, 0)),
        (Date(2020, 4, 30), Period(0, 1, 0)),
        (Date(2020, 12, 31), Period(0, 1, 0)),
        (Date(2020, 6, 15), Period(0, 0, 5)),
        (Date(2020, 12, 31), Period(0, 0, 1)),
        (Date(2020, 3, 1), Period(0, 0, -1)),
        (Date(2020, 3, 1), Period(0, -1, 0)),
        (Date(2020, 3, 1), Period(-1, 0, 0)),
        (Date(2020, 1, 15), Period(0, 0, 50)),
        (Date(2020, 1, 15), Period(0, 0, 100)),
        (Date(2021, 1, 15), Period(0, 0, 50)),
        (Date(2020, 6, 15), Period(0, 0, 200)),
        (Date(2020, 6, 15), Period(0, 0, 400)),
        (Date(2020, 6, 15), Period(0, 0, -50)),
        (Date(2020, 6, 15), Period(0, 0, -100)),
        (Date(2020, 6, 15), Period(0, 0, -200)),
        (Date(2020, 2, 29), Period(0, 0, -60)),
        (Date(2020, 1, 31), Period(0, 1, 0)),
        (Date(2021, 1, 31), Period(0, 1, 0)),
        (Date(2020, 3, 31), Period(0, 1, 0)),
        (Date(2020, 4, 30), Period(0, 1, 0)),
        (Date(2020, 5, 31), Period(0, 1, 0)),
        (Date(2020, 7, 31), Period(0, 1, 0)),
        (Date(2020, 8, 31), Period(0, 1, 0)),
        (Date(2020, 9, 30), Period(0, 1, 0)),
        (Date(2020, 10, 31), Period(0, 1, 0)),
        (Date(2020, 11, 30), Period(0, 1, 0)),
        (Date(2020, 12, 31), Period(0, 1, 0)),
        (Date(2020, 1, 31), Period(0, 13, 0)),
        (Date(2020, 12, 31), Period(0, 0, 1)),
        (Date(2020, 12, 31), Period(0, 0, 2)),
        (Date(2021, 1, 1), Period(0, 0, -1)),
        (Date(2021, 1, 1), Period(0, 0, -2)),
        (Date(2020, 2, 28), Period(0, 0, 1)),
        (Date(2020, 2, 29), Period(0, 0, 1)),
        (Date(2021, 2, 28), Period(0, 0, 1)),
        (Date(2020, 3, 1), Period(0, 0, -1)),
        (Date(2021, 3, 1), Period(0, 0, -1)),
        (Date(2020, 1, 15), Period(0, 12, 0)),
        (Date(2020, 1, 15), Period(0, 24, 0)),
        (Date(2020, 2, 29), Period(0, 12, 0)),
        (Date(2020, 2, 29), Period(0, 48, 0)),
        (Date(2020, 1, 15), Period(0, 120, 0)),
        (Date(2020, 6, 15), Period(1, 0, 0)),
        (Date(2020, 6, 15), Period(4, 0, 0)),
        (Date(2020, 2, 29), Period(1, 0, 0)),
        (Date(2020, 2, 29), Period(4, 0, 0)),
        (Date(2020, 1, 31), Period(1, 1, 1)),
        (Date(2020, 2, 29), Period(1, 1, 1)),
        (Date(2020, 12, 31), Period(0, 0, 32)),
        (Date(2020, 12, 31), Period(0, 0, 62)),
        (Date(2020, 1, 1), Period(0, 0, -1)),
        (Date(2020, 1, 1), Period(0, 0, -32)),
        (Date(2020, 3, 1), Period(0, -1, 0)),
        (Date(2020, 3, 1), Period(0, -2, 0)),
        (Date(2020, 3, 1), Period(-1, 0, 0)),
        (Date(2020, 2, 29), Period(-1, 0, 0)),
        (Date(2020, 1, 30), Period(0, 1, 1)),
        (Date(2021, 1, 30), Period(0, 1, 1)),
        (Date(2020, 4, 30), Period(0, 1, 1)),
        (Date(2020, 5, 31), Period(0, 1, 1)),
        (Date(2020, 2, 29), Period(1, 0, 0)),
        (Date(2024, 2, 29), Period(1, 0, 0)),
        (Date(2020, 2, 29), Period(4, 0, 0)),
        (Date(2020, 2, 29), Period(2, 0, 0)),
        (Date(2020, 2, 29), Period(3, 0, 0)),
        (Date(2020, 2, 29), Period(5, 0, 0)),
        (Date(2020, 2, 29), Period(8, 0, 0)),
        (Date(2020, 1, 31), Period(0, 1, 0)),
        (Date(2020, 2, 29), Period(0, 1, 0)),
        (Date(2020, 3, 31), Period(0, 1, 0)),
        (Date(2020, 4, 30), Period(0, 1, 0)),
        (Date(2020, 5, 31), Period(0, 1, 0)),
        (Date(2020, 6, 30), Period(0, 1, 0)),
        (Date(2020, 7, 31), Period(0, 1, 0)),
        (Date(2020, 8, 31), Period(0, 1, 0)),
        (Date(2020, 9, 30), Period(0, 1, 0)),
        (Date(2020, 10, 31), Period(0, 1, 0)),
        (Date(2020, 11, 30), Period(0, 1, 0)),
        (Date(2020, 12, 31), Period(0, 1, 0)),
        # Added mixed-component (all non-zero) periods for decomposition coverage
        (Date(2020, 1, 15), Period(1, 1, 1)),
        (Date(2021, 1, 15), Period(1, 1, 1)),
        (Date(2020, 1, 31), Period(2, 2, 1)),
        (Date(2019, 12, 30), Period(2, 2, 1)),
        (Date(2020, 2, 29), Period(1, 2, 1)),
        (Date(2020, 3, 31), Period(1, 1, 2)),
        (Date(2020, 8, 31), Period(1, 1, 2)),
        (Date(2020, 11, 30), Period(1, 2, 3)),
        (Date(2021, 1, 30), Period(1, 2, 3)),
        (Date(2020, 12, 31), Period(1, 2, 3)),
        (Date(2020, 5, 31), Period(2, 3, 4)),
        (Date(2021, 7, 31), Period(2, 3, 4)),
        (Date(2020, 1, 15), Period(-1, -1, -1)),
        (Date(2020, 12, 15), Period(-1, -1, -1)),
        (Date(2020, 3, 31), Period(-1, -1, -1)),
        (Date(2020, 1, 15), Period(1, -2, 3)),
        (Date(2020, 6, 15), Period(-1, 2, -3)),
        (Date(2020, 2, 29), Period(1, -1, 1)),
        (Date(2020, 2, 29), Period(-1, 1, -1)),
        (Date(2020, 1, 15), Period(3, 14, 40)),
        (Date(2020, 6, 15), Period(3, 14, 40)),
        (Date(2020, 1, 31), Period(1, 13, 31)),
        (Date(2020, 2, 29), Period(1, 13, 31)),
        (Date(2020, 8, 31), Period(1, 13, 31)),
        (Date(2020, 1, 15), Period(4, -13, 15)),
        (Date(2020, 12, 15), Period(4, -13, 15)),
        (Date(2020, 1, 30), Period(1, 1, 1)),
        (Date(2020, 1, 30), Period(2, 1, 2)),
        (Date(2021, 1, 30), Period(2, 1, 2)),
        (Date(2020, 4, 30), Period(2, 1, 2)),
        (Date(2020, 5, 31), Period(2, 1, 2)),
    ]


def python_date_plus(base: Date, per: Period) -> Date:
    py_base = base.to_python_date()
    py_res = py_base + relativedelta(years=per.years, months=per.months, days=per.days)
    return Date.from_python_date(py_res)


def python_date_plus_sequence(base: Date, seq: list[Period], label: str) -> Date:
    """Apply a sequence of periods via Python datetime + relativedelta."""
    cur = base
    for p in seq:
        cur = python_date_plus(cur, p)
    return cur


def generate_decomposed_orders(per: Period):
    """Generate decomposed period addition orders for (Y,M,D), skipping zero components."""
    components = []
    if per.years != 0:
        components.append(("Y", Period(per.years, 0, 0)))
    if per.months != 0:
        components.append(("M", Period(0, per.months, 0)))
    if per.days != 0:
        components.append(("D", Period(0, 0, per.days)))

    if not components:
        return [("ID", [])]  # Identity order for zero period

    orders = []
    for order in permutations(components, len(components)):
        label = "->".join([k for k, _ in order])
        orders.append((label, [p for _, p in order]))
    return orders


def all_decomposed_cases():
    cases = []
    for base, per in get_period_arithmetic_test_cases():
        for label, seq in generate_decomposed_orders(per):
            cases.append((base, per, label, seq))
    return cases


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"py_ref_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
def test_python_decomposed_orders(
    base: Date, per: Period, label: str, seq: list[Period]
):
    """Ensure Python results are well-defined for each decomposed order (sanity)."""
    got = python_date_plus_sequence(base, seq, label)
    assert isinstance(got, Date)


def _solve_decomposed_with_solver(solver_cls, base: Date, seq: list[Period]):
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


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"baseline_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.baseline
def test_baseline_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = python_date_plus_sequence(base, seq, label)
    model = _solve_decomposed_with_solver(BaselineSolver, base, seq)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Baseline order {label}: {base} + {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"epoch_days_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.epoch_days
def test_epoch_days_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = python_date_plus_sequence(base, seq, label)
    model = _solve_decomposed_with_solver(EpochDaysSolver, base, seq)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Epoch_days order {label}: {base} + {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"hybrid_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.hybrid
def test_hybrid_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = python_date_plus_sequence(base, seq, label)
    model = _solve_decomposed_with_solver(HybridDateSolver, base, seq)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Hybrid order {label}: {base} + {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"ab_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.alpha_beta
def test_alpha_beta_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = python_date_plus_sequence(base, seq, label)
    model = _solve_decomposed_with_solver(AlphaBetaSolver, base, seq)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Alpha_beta order {label}: {base} + {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"alpha_beta_table_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.alpha_beta_table
def test_alpha_beta_table_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = python_date_plus_sequence(base, seq, label)
    model = _solve_decomposed_with_solver(AlphaBetaTableSolver, base, seq)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"alpha_beta_table order {label}: {base} + {per} -> {got}, expected {expect}"
