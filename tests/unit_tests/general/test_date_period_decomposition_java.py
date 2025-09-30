import shutil
import subprocess
from itertools import permutations
from pathlib import Path

import pytest

from datesmt.core import Date, Period
from datesmt.symbolic_advanced import AdvancedDateSolver
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
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
        (Date(2020, 6, 15), Period(80, 0, 0)),
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


JAVA_DIR = Path(__file__).resolve().parent / "java"
JAVA_SRC = JAVA_DIR / "LocalDateGroundTruth.java"
JAVA_CLASS = JAVA_DIR / "LocalDateGroundTruth.class"


def ensure_java_available_and_compiled():
    if shutil.which("javac") is None or shutil.which("java") is None:
        pytest.skip(
            "Java toolchain (javac/java) not available; skipping Java ground truth checks"
        )

    if not JAVA_SRC.exists():
        pytest.skip(
            f"Java source not found at {JAVA_SRC}; skipping Java ground truth checks"
        )

    needs_compile = (not JAVA_CLASS.exists()) or (
        JAVA_CLASS.stat().st_mtime < JAVA_SRC.stat().st_mtime
    )
    if needs_compile:
        JAVA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["javac", "LocalDateGroundTruth.java"],
                cwd=str(JAVA_DIR),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            pytest.skip(f"Failed to compile Java ground truth helper: {e.stderr}")


# Simple cache to avoid recomputing Java results across tests
_JAVA_DECOMP_CACHE = {}


def _cache_key(base: Date, per: Period, label: str):
    return (base.year, base.month, base.day, per.years, per.months, per.days, label)


def java_localdate_plus(base: Date, per: Period) -> Date:
    ensure_java_available_and_compiled()
    try:
        proc = subprocess.run(
            [
                "java",
                "-cp",
                str(JAVA_DIR),
                "LocalDateGroundTruth",
                str(base.year),
                str(base.month),
                str(base.day),
                str(per.years),
                str(per.months),
                str(per.days),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Java helper execution failed: {e.stderr}")

    out = proc.stdout.strip()
    try:
        y_str, m_str, d_str = out.split("-")
        return Date(int(y_str), int(m_str), int(d_str))
    except Exception as e:
        pytest.skip(f"Unexpected Java output: '{out}' ({e})")


def java_localdate_plus_sequence(base: Date, seq: list[Period], label: str) -> Date:
    """Apply a sequence of periods via Java, returning the final LocalDate (with cache)."""
    key = _cache_key(
        base,
        Period(
            sum(p.years for p in seq),
            sum(p.months for p in seq),
            sum(p.days for p in seq),
        ),
        label,
    )
    if key in _JAVA_DECOMP_CACHE:
        return _JAVA_DECOMP_CACHE[key]

    cur = base
    for p in seq:
        cur = java_localdate_plus(cur, p)

    _JAVA_DECOMP_CACHE[key] = cur
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
        pytest.param(base, per, label, seq, id=f"java_ref_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
def test_java_decomposed_orders(base: Date, per: Period, label: str, seq: list[Period]):
    """Ensure Java results are well-defined for each decomposed order (sanity)."""
    got = java_localdate_plus_sequence(base, seq, label)
    assert isinstance(got, Date)


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
    expect = java_localdate_plus_sequence(base, seq, label)

    s = BaselineSolver()
    x = s.add_date_var("x")
    s.add_constraint(x == base)

    current = x
    for i, p in enumerate(seq):
        t = s.add_date_var(f"t{i}")
        s.add_constraint(t == current + p)
        current = t

    y = s.add_date_var("y")
    s.add_constraint(y == current)

    model = s.solve()
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Baseline order {label}: {base} + {per} -> {got}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,label,seq",
    [
        pytest.param(base, per, label, seq, id=f"advanced_{base}+{per}_{label}")
        for base, per, label, seq in all_decomposed_cases()
    ],
)
@pytest.mark.advanced
def test_advanced_matches_java_decomposed(
    base: Date, per: Period, label: str, seq: list[Period]
):
    expect = java_localdate_plus_sequence(base, seq, label)

    s = AdvancedDateSolver()
    x = s.add_date_var("x")
    s.add_constraint(x == base)

    current = x
    for i, p in enumerate(seq):
        t = s.add_date_var(f"t{i}")
        s.add_constraint(t == current + p)
        current = t

    y = s.add_date_var("y")
    s.add_constraint(y == current)

    model = s.solve()
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Advanced order {label}: {base} + {per} -> {got}, expected {expect}"


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
    expect = java_localdate_plus_sequence(base, seq, label)

    s = HybridDateSolver()
    x = s.new_date("x")
    s.add_constraint(x == base)

    current = x
    for i, p in enumerate(seq):
        t = s.new_date(f"t{i}")
        s.add_constraint(t == current + p)
        current = t

    y = s.new_date("y")
    s.add_constraint(y == current)

    model = s.solve()
    assert model["status"] == "sat"
    got = model["dates"]["y"]
    assert (
        got == expect
    ), f"Hybrid order {label}: {base} + {per} -> {got}, expected {expect}"
