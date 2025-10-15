import pytest
from dateutil.relativedelta import relativedelta

from datesmt_int.core import Date, Period
from datesmt_int.symbolic_alpha_beta import AlphaBetaSolver
from datesmt_int.symbolic_alpha_beta_table import AlphaBetaTableSolver
from datesmt_int.symbolic_baseline import BaselineSolver
from datesmt_int.symbolic_epoch_days import EpochDaysSolver
from datesmt_int.symbolic_hybrid import HybridSolver

# Reuse canonical test cases locally (migrated from test_date_period_operation.py)


def get_period_arithmetic_test_cases():
    """Get all period arithmetic test cases for date + period operation testing."""
    return [
        # Basic mixed components
        (Date(2020, 6, 15), Period(1, 2, 3), Date(2021, 8, 18)),
        (Date(2020, 6, 15), Period(2, 6, 10), Date(2022, 12, 25)),
        (Date(2020, 6, 15), Period(-1, -2, -3), Date(2019, 4, 12)),
        # Leap & month-boundary behaviors under Y→M→D
        (Date(2020, 2, 29), Period(1, 0, 0), Date(2021, 2, 28)),
        (Date(2020, 1, 31), Period(0, 1, 0), Date(2020, 2, 29)),
        (Date(2020, 4, 30), Period(0, 1, 0), Date(2020, 5, 30)),
        (Date(2020, 12, 31), Period(0, 1, 0), Date(2021, 1, 31)),
        # boundaries (1900, 2100)
        (Date(1900, 3, 31), Period(0, 1, 0), Date(1900, 4, 30)),
        (Date(1900, 3, 31), Period(0, 0, 1), Date(1900, 4, 1)),
        (Date(1900, 3, 2), Period(0, 0, -1), Date(1900, 3, 1)),
        (Date(2100, 1, 31), Period(0, 1, 0), Date(2100, 2, 28)),
        (Date(2100, 2, 28), Period(0, 0, -1), Date(2100, 2, 27)),
        # Days-only & simple edges
        (Date(2020, 6, 15), Period(0, 0, 5), Date(2020, 6, 20)),
        (Date(2020, 12, 31), Period(0, 0, 1), Date(2021, 1, 1)),
        (Date(2020, 3, 1), Period(0, 0, -1), Date(2020, 2, 29)),
        (Date(2020, 3, 1), Period(0, -1, 0), Date(2020, 2, 1)),
        (Date(2020, 3, 1), Period(-1, 0, 0), Date(2019, 3, 1)),
        # Large day additions (crossing multiple months)
        (Date(2020, 1, 15), Period(0, 0, 50), Date(2020, 3, 5)),
        (Date(2020, 1, 15), Period(0, 0, 100), Date(2020, 4, 24)),
        (Date(2021, 1, 15), Period(0, 0, 50), Date(2021, 3, 6)),
        (Date(2020, 6, 15), Period(0, 0, 200), Date(2021, 1, 1)),
        (Date(2020, 6, 15), Period(0, 0, 400), Date(2021, 7, 20)),
        # Large day subtractions (crossing multiple months)
        (Date(2020, 6, 15), Period(0, 0, -50), Date(2020, 4, 26)),
        (Date(2020, 6, 15), Period(0, 0, -100), Date(2020, 3, 7)),
        (Date(2020, 6, 15), Period(0, 0, -200), Date(2019, 11, 28)),
        (Date(2020, 2, 29), Period(0, 0, -60), Date(2019, 12, 31)),
        # Month-end to month-end transitions
        (Date(2020, 1, 31), Period(0, 1, 0), Date(2020, 2, 29)),
        (Date(2021, 1, 31), Period(0, 1, 0), Date(2021, 2, 28)),
        (Date(2020, 3, 31), Period(0, 1, 0), Date(2020, 4, 30)),
        (Date(2020, 4, 30), Period(0, 1, 0), Date(2020, 5, 30)),
        (Date(2020, 5, 31), Period(0, 1, 0), Date(2020, 6, 30)),
        (Date(2020, 7, 31), Period(0, 1, 0), Date(2020, 8, 31)),
        (Date(2020, 8, 31), Period(0, 1, 0), Date(2020, 9, 30)),
        (Date(2020, 9, 30), Period(0, 1, 0), Date(2020, 10, 30)),
        (Date(2020, 10, 31), Period(0, 1, 0), Date(2020, 11, 30)),
        (Date(2020, 11, 30), Period(0, 1, 0), Date(2020, 12, 30)),
        (Date(2020, 12, 31), Period(0, 1, 0), Date(2021, 1, 31)),
        (Date(2020, 12, 31), Period(0, 1, 0), Date(2021, 1, 31)),
        (Date(2020, 1, 31), Period(0, 13, 0), Date(2021, 2, 28)),
        # Year boundary transitions
        (Date(2020, 12, 31), Period(0, 0, 1), Date(2021, 1, 1)),
        (Date(2020, 12, 31), Period(0, 0, 2), Date(2021, 1, 2)),
        (Date(2021, 1, 1), Period(0, 0, -1), Date(2020, 12, 31)),
        (Date(2021, 1, 1), Period(0, 0, -2), Date(2020, 12, 30)),
        (Date(2021, 1, 1), Period(0, 0, -2), Date(2020, 12, 30)),
        # February leap year edge cases
        (Date(2020, 2, 28), Period(0, 0, 1), Date(2020, 2, 29)),
        (Date(2020, 2, 29), Period(0, 0, 1), Date(2020, 3, 1)),
        (Date(2021, 2, 28), Period(0, 0, 1), Date(2021, 3, 1)),
        (Date(2020, 3, 1), Period(0, 0, -1), Date(2020, 2, 29)),
        (Date(2021, 2, 28), Period(0, 0, 1), Date(2021, 3, 1)),
        (Date(2021, 3, 1), Period(0, 0, -1), Date(2021, 2, 28)),
        (Date(2020, 3, 1), Period(0, 0, -1), Date(2020, 2, 29)),
        (Date(2021, 3, 1), Period(0, 0, -1), Date(2021, 2, 28)),
        # Large month additions
        (Date(2020, 1, 15), Period(0, 12, 0), Date(2021, 1, 15)),
        (Date(2020, 1, 15), Period(0, 24, 0), Date(2022, 1, 15)),
        (Date(2020, 2, 29), Period(0, 12, 0), Date(2021, 2, 28)),
        (Date(2020, 2, 29), Period(0, 48, 0), Date(2024, 2, 29)),
        (Date(2020, 1, 15), Period(0, 120, 0), Date(2030, 1, 15)),
        # Large year additions
        (Date(2020, 6, 15), Period(1, 0, 0), Date(2021, 6, 15)),
        (Date(2020, 6, 15), Period(4, 0, 0), Date(2024, 6, 15)),
        (Date(2020, 2, 29), Period(1, 0, 0), Date(2021, 2, 28)),
        (Date(2020, 2, 29), Period(4, 0, 0), Date(2024, 2, 29)),
        (Date(2020, 6, 15), Period(79, 0, 0), Date(2099, 6, 15)),
        # Complex mixed cases
        (Date(2020, 1, 31), Period(1, 1, 1), Date(2021, 3, 1)),
        (Date(2020, 2, 29), Period(1, 1, 1), Date(2021, 3, 30)),
        (Date(2020, 12, 31), Period(0, 0, 32), Date(2021, 2, 1)),
        (Date(2020, 12, 31), Period(0, 0, 62), Date(2021, 3, 3)),
        # Negative period edge cases
        (Date(2020, 1, 1), Period(0, 0, -1), Date(2019, 12, 31)),
        (Date(2020, 1, 1), Period(0, 0, -32), Date(2019, 11, 30)),
        (Date(2020, 3, 1), Period(0, -1, 0), Date(2020, 2, 1)),
        (Date(2020, 3, 1), Period(0, -2, 0), Date(2020, 1, 1)),
        (Date(2020, 3, 1), Period(0, -2, 0), Date(2020, 1, 1)),
        (Date(2020, 3, 1), Period(-1, 0, 0), Date(2019, 3, 1)),
        (Date(2020, 3, 1), Period(-1, 0, 0), Date(2019, 3, 1)),
        (Date(2020, 2, 29), Period(-1, 0, 0), Date(2019, 2, 28)),
        # Edge cases around month boundaries with days
        (Date(2020, 1, 30), Period(0, 1, 1), Date(2020, 3, 1)),
        (Date(2021, 1, 30), Period(0, 1, 1), Date(2021, 3, 1)),
        (Date(2020, 4, 30), Period(0, 1, 1), Date(2020, 5, 31)),
        (Date(2020, 5, 31), Period(0, 1, 1), Date(2020, 7, 1)),
        # Additional edge cases for comprehensive coverage
        # Year jumps across leap years
        (Date(2020, 2, 29), Period(1, 0, 0), Date(2021, 2, 28)),
        (Date(2024, 2, 29), Period(1, 0, 0), Date(2025, 2, 28)),
        (Date(2020, 2, 29), Period(4, 0, 0), Date(2024, 2, 29)),
        (Date(2020, 2, 29), Period(2, 0, 0), Date(2022, 2, 28)),
        (Date(2020, 2, 29), Period(3, 0, 0), Date(2023, 2, 28)),
        (Date(2020, 2, 29), Period(5, 0, 0), Date(2025, 2, 28)),
        (Date(2020, 2, 29), Period(8, 0, 0), Date(2028, 2, 29)),
        # Month jumps with varying lengths - comprehensive coverage
        (Date(2020, 1, 31), Period(0, 1, 0), Date(2020, 2, 29)),
        (Date(2021, 1, 31), Period(0, 1, 0), Date(2021, 2, 28)),
        (Date(2020, 1, 31), Period(0, 2, 0), Date(2020, 3, 31)),
        (Date(2020, 1, 31), Period(0, 3, 0), Date(2020, 4, 30)),
        (Date(2020, 1, 31), Period(0, 12, 0), Date(2021, 1, 31)),
        # Four-year cycle math for leap years
        (Date(2020, 2, 29), Period(1, 0, 0), Date(2021, 2, 28)),
        (Date(2020, 2, 29), Period(2, 0, 0), Date(2022, 2, 28)),
        (Date(2020, 2, 29), Period(3, 0, 0), Date(2023, 2, 28)),
        (Date(2020, 2, 29), Period(4, 0, 0), Date(2024, 2, 29)),
        (Date(2020, 2, 29), Period(5, 0, 0), Date(2025, 2, 28)),
        (Date(2020, 2, 29), Period(8, 0, 0), Date(2028, 2, 29)),
        # Month lookup path validation - all months with max days
        (Date(2020, 1, 31), Period(0, 1, 0), Date(2020, 2, 29)),
        (Date(2020, 2, 29), Period(0, 1, 0), Date(2020, 3, 29)),
        (Date(2020, 3, 31), Period(0, 1, 0), Date(2020, 4, 30)),
        (Date(2020, 4, 30), Period(0, 1, 0), Date(2020, 5, 30)),
        (Date(2020, 5, 31), Period(0, 1, 0), Date(2020, 6, 30)),
        (Date(2020, 6, 30), Period(0, 1, 0), Date(2020, 7, 30)),
        (Date(2020, 7, 31), Period(0, 1, 0), Date(2020, 8, 31)),
        (Date(2020, 8, 31), Period(0, 1, 0), Date(2020, 9, 30)),
        (Date(2020, 9, 30), Period(0, 1, 0), Date(2020, 10, 30)),
        (Date(2020, 10, 31), Period(0, 1, 0), Date(2020, 11, 30)),
        (Date(2020, 11, 30), Period(0, 1, 0), Date(2020, 12, 30)),
        (Date(2020, 12, 31), Period(0, 1, 0), Date(2021, 1, 31)),
    ]


def python_date_plus(base: Date, per: Period) -> Date:
    """Compute base + period using Python's datetime + relativedelta."""
    py_base = base.to_python_date()
    py_res = py_base + relativedelta(years=per.years, months=per.months, days=per.days)
    # Constrain to supported domain if needed; tests stay within range
    return Date.from_python_date(py_res)


def _solve_single_add(solver_cls, base: Date, per: Period) -> dict:
    s = solver_cls()
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x == base)
    s.add_constraint(y == x + per)

    return s.solve()


def _solve_single_radd(solver_cls, base: Date, per: Period) -> dict:
    s = solver_cls()
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x == base)
    s.add_constraint(y == per + x)
    return s.solve()


def _solve_single_sub(solver_cls, base: Date, per: Period) -> dict:
    s = solver_cls()
    x = s.add_date_var("x")
    y = s.add_date_var("y")
    s.add_constraint(x == base)
    s.add_constraint(y == x - per)
    return s.solve()


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"py_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
def test_python_output_equals_ground_truth(base: Date, per: Period, expect: Date):
    """Assert Python date + relativedelta equals the expected canonical ground truth."""
    py_got = python_date_plus(base, per)
    assert (
        py_got == expect
    ), f"Python date+relativedelta: {base} + {per} -> {py_got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.baseline
@pytest.mark.integer
def test_baseline_equals_ground_truth(base: Date, per: Period, expect: Date):
    rb = _solve_single_add(BaselineSolver, base, per)
    assert rb["status"] == "sat"
    got_b = rb["dates"]["y"]
    assert got_b == expect, f"Baseline: {base} + {per} -> {got_b}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.epoch_days
@pytest.mark.integer
def test_epoch_days_equals_ground_truth(base: Date, per: Period, expect: Date):
    ra = _solve_single_add(EpochDaysSolver, base, per)
    assert ra["status"] == "sat"
    got_a = ra["dates"]["y"]
    assert got_a == expect, f"Epoch_days: {base} + {per} -> {got_a}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.hybrid
@pytest.mark.integer
def test_hybrid_equals_ground_truth(base: Date, per: Period, expect: Date):
    rh = _solve_single_add(HybridSolver, base, per)
    assert rh["status"] == "sat"
    got_h = rh["dates"]["y"]
    assert got_h == expect, f"Hybrid: {base} + {per} -> {got_h}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_equals_ground_truth(base: Date, per: Period, expect: Date):
    ra = _solve_single_add(AlphaBetaSolver, base, per)
    assert ra["status"] == "sat"
    got_a = ra["dates"]["y"]
    assert got_a == expect, f"Alpha_beta: {base} + {per} -> {got_a}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_table_equals_ground_truth(base: Date, per: Period, expect: Date):
    ra = _solve_single_add(AlphaBetaTableSolver, base, per)
    assert ra["status"] == "sat"
    got_a = ra["dates"]["y"]
    assert (
        got_a == expect
    ), f"alpha_beta_table: {base} + {per} -> {got_a}, expected {expect}"


# radd: Period + Date
@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"radd_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.baseline
@pytest.mark.integer
def test_baseline_radd_equals_ground_truth(base: Date, per: Period, expect: Date):
    model = _solve_single_radd(BaselineSolver, base, per)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"Baseline radd: {per} + {base} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"radd_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.epoch_days
@pytest.mark.integer
def test_epoch_days_radd_equals_ground_truth(base: Date, per: Period, expect: Date):
    model = _solve_single_radd(EpochDaysSolver, base, per)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"EpochDays radd: {per} + {base} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"radd_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.hybrid
@pytest.mark.integer
def test_hybrid_radd_equals_ground_truth(base: Date, per: Period, expect: Date):
    model = _solve_single_radd(HybridSolver, base, per)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"Hybrid radd: {per} + {base} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"radd_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_radd_equals_ground_truth(base: Date, per: Period, expect: Date):
    model = _solve_single_radd(AlphaBetaSolver, base, per)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"AlphaBeta radd: {per} + {base} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"radd_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_table_radd_equals_ground_truth(
    base: Date, per: Period, expect: Date
):
    model = _solve_single_radd(AlphaBetaTableSolver, base, per)
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"AlphaBetaTable radd: {per} + {base} -> {got}, expected {expect}"


# sub: Date - Period (equivalent to add negative period). If ground truth is out of domain, expect UNSAT.
@pytest.mark.parametrize(
    "base,per",
    [
        pytest.param(base, per, id=f"sub_{base}-{per}")
        for base, per, _ in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.baseline
@pytest.mark.integer
def test_baseline_subtract_matches_python(base: Date, per: Period):
    model = _solve_single_sub(BaselineSolver, base, per)
    try:
        expect = python_date_plus(base, Period(-per.years, -per.months, -per.days))
    except ValueError:
        assert model["status"] == "unsat"
        return
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"Baseline sub: {base} - {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per",
    [
        pytest.param(base, per, id=f"sub_{base}-{per}")
        for base, per, _ in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.epoch_days
@pytest.mark.integer
def test_epoch_days_subtract_matches_python(base: Date, per: Period):
    model = _solve_single_sub(EpochDaysSolver, base, per)
    try:
        expect = python_date_plus(base, Period(-per.years, -per.months, -per.days))
    except ValueError:
        assert model["status"] == "unsat"
        return
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"EpochDays sub: {base} - {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per",
    [
        pytest.param(base, per, id=f"sub_{base}-{per}")
        for base, per, _ in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.hybrid
@pytest.mark.integer
def test_hybrid_subtract_matches_python(base: Date, per: Period):
    model = _solve_single_sub(HybridSolver, base, per)
    try:
        expect = python_date_plus(base, Period(-per.years, -per.months, -per.days))
    except ValueError:
        assert model["status"] == "unsat"
        return
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"Hybrid sub: {base} - {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per",
    [
        pytest.param(base, per, id=f"sub_{base}-{per}")
        for base, per, _ in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_subtract_matches_python(base: Date, per: Period):
    model = _solve_single_sub(AlphaBetaSolver, base, per)
    try:
        expect = python_date_plus(base, Period(-per.years, -per.months, -per.days))
    except ValueError:
        assert model["status"] == "unsat"
        return
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert got == expect, f"AlphaBeta sub: {base} - {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per",
    [
        pytest.param(base, per, id=f"sub_{base}-{per}")
        for base, per, _ in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.alpha_beta
@pytest.mark.integer
def test_alpha_beta_table_subtract_matches_python(base: Date, per: Period):
    model = _solve_single_sub(AlphaBetaTableSolver, base, per)
    try:
        expect = python_date_plus(base, Period(-per.years, -per.months, -per.days))
    except ValueError:
        assert model["status"] == "unsat"
        return
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"AlphaBetaTable sub: {base} - {per} -> {got}, expected {expect}"
