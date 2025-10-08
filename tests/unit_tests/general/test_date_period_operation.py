import pytest
from dateutil.relativedelta import relativedelta

from datesmt.core import Date, Period
from datesmt.symbolic_advanced import AdvancedDateSolver
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_hybrid import HybridDateSolver
from datesmt.symbolic_ab import AbDateSolver

# Reuse canonical test cases locally (migrated from test_date_period_operation.py)


def get_period_arithmetic_test_cases():
    """Get all period arithmetic test cases for date + period operation testing."""
    return [
        # Basic mixed components
        (Date(2020, 6, 15), Period(1, 2, 3), Date(2021, 8, 18)),
        (Date(2020, 6, 15), Period(2, 6, 10), Date(2022, 12, 25)),
        (Date(2020, 6, 15), Period(-1, -2, -3), Date(2019, 4, 12)),
        # Leap & month-boundary behaviors under Y→M→D
        (
            Date(2020, 2, 29),
            Period(1, 0, 0),
            Date(2021, 2, 28),
        ),  # with RoundDown policy
        (Date(2020, 1, 31), Period(0, 1, 0), Date(2020, 2, 29)),  # test with leap year
        (Date(2020, 4, 30), Period(0, 1, 0), Date(2020, 5, 30)),
        (Date(2020, 12, 31), Period(0, 1, 0), Date(2021, 1, 31)),
        # Days-only & simple edges
        (Date(2020, 6, 15), Period(0, 0, 5), Date(2020, 6, 20)),
        (Date(2020, 12, 31), Period(0, 0, 1), Date(2021, 1, 1)),
        (Date(2020, 3, 1), Period(0, 0, -1), Date(2020, 2, 29)),
        (Date(2020, 3, 1), Period(0, -1, 0), Date(2020, 2, 1)),
        (Date(2020, 3, 1), Period(-1, 0, 0), Date(2019, 3, 1)),
        # Large day additions (crossing multiple months)
        (
            Date(2020, 1, 15),
            Period(0, 0, 50),
            Date(2020, 3, 5),
        ),  # Jan 15 + 50 days = Mar 5 for 2020
        (
            Date(2020, 1, 15),
            Period(0, 0, 100),
            Date(2020, 4, 24),
        ),  # Jan 15 + 100 days = Apr 24 for 2020
        (
            Date(2021, 1, 15),
            Period(0, 0, 50),
            Date(2021, 3, 6),
        ),  # Jan 15 + 50 days = Mar 6 for 2021
        (
            Date(2020, 6, 15),
            Period(0, 0, 200),
            Date(2021, 1, 1),
        ),  # Jun 15 + 200 days = Jan 1 next year
        (
            Date(2020, 6, 15),
            Period(0, 0, 400),
            Date(2021, 7, 20),
        ),  # 400 days from Jun 15, 2020
        # Large day subtractions (crossing multiple months)
        (
            Date(2020, 6, 15),
            Period(0, 0, -50),
            Date(2020, 4, 26),
        ),  # Jun 15 - 50 days = Apr 26
        (
            Date(2020, 6, 15),
            Period(0, 0, -100),
            Date(2020, 3, 7),
        ),  # Jun 15 - 100 days = Mar 7
        (
            Date(2020, 6, 15),
            Period(0, 0, -200),
            Date(2019, 11, 28),
        ),  # Jun 15 - 200 days = Nov 28 prev year
        (
            Date(2020, 2, 29),
            Period(0, 0, -60),
            Date(2019, 12, 31),
        ),  # 60 days before Feb 29, 2020
        # Month-end to month-end transitions
        (
            Date(2020, 1, 31),
            Period(0, 1, 0),
            Date(2020, 2, 29),
        ),  # Jan 31 + 1 month = Feb 29 (leap year)
        (
            Date(2021, 1, 31),
            Period(0, 1, 0),
            Date(2021, 2, 28),
        ),  # Jan 31 + 1 month = Feb 28 (non-leap year)
        (
            Date(2020, 3, 31),
            Period(0, 1, 0),
            Date(2020, 4, 30),
        ),  # Mar 31 + 1 month = Apr 30
        (
            Date(2020, 4, 30),
            Period(0, 1, 0),
            Date(2020, 5, 30),
        ),  # Apr 30 + 1 month = May 30
        (
            Date(2020, 5, 31),
            Period(0, 1, 0),
            Date(2020, 6, 30),
        ),  # May 31 + 1 month = Jun 30
        (
            Date(2020, 7, 31),
            Period(0, 1, 0),
            Date(2020, 8, 31),
        ),  # Jul 31 + 1 month = Aug 31
        (
            Date(2020, 8, 31),
            Period(0, 1, 0),
            Date(2020, 9, 30),
        ),  # Aug 31 + 1 month = Sep 30
        (
            Date(2020, 9, 30),
            Period(0, 1, 0),
            Date(2020, 10, 30),
        ),  # Sep 30 + 1 month = Oct 30
        (
            Date(2020, 10, 31),
            Period(0, 1, 0),
            Date(2020, 11, 30),
        ),  # Oct 31 + 1 month = Nov 30
        (
            Date(2020, 11, 30),
            Period(0, 1, 0),
            Date(2020, 12, 30),
        ),  # Nov 30 + 1 month = Dec 30
        (
            Date(2020, 12, 31),
            Period(0, 1, 0),
            Date(2021, 1, 31),
        ),  # Dec 31 + 1 month = Jan 31 next year
        (
            Date(2020, 1, 31),
            Period(0, 13, 0),
            Date(2021, 2, 28),
        ),  # Jan 31 + 13 months = Feb 28 (non-leap year)
        # Year boundary transitions
        (
            Date(2020, 12, 31),
            Period(0, 0, 1),
            Date(2021, 1, 1),
        ),  # Dec 31 + 1 day = Jan 1 next year
        (
            Date(2020, 12, 31),
            Period(0, 0, 2),
            Date(2021, 1, 2),
        ),  # Dec 31 + 2 days = Jan 2 next year
        (
            Date(2021, 1, 1),
            Period(0, 0, -1),
            Date(2020, 12, 31),
        ),  # Jan 1 - 1 day = Dec 31 prev year
        (
            Date(2021, 1, 1),
            Period(0, 0, -2),
            Date(2020, 12, 30),
        ),  # Jan 1 - 2 days = Dec 30 prev year
        # February leap year edge cases
        (
            Date(2020, 2, 28),
            Period(0, 0, 1),
            Date(2020, 2, 29),
        ),  # Feb 28 + 1 day = Feb 29 (leap year)
        (
            Date(2020, 2, 29),
            Period(0, 0, 1),
            Date(2020, 3, 1),
        ),  # Feb 29 + 1 day = Mar 1 (leap year)
        (
            Date(2021, 2, 28),
            Period(0, 0, 1),
            Date(2021, 3, 1),
        ),  # Feb 28 + 1 day = Mar 1 (non-leap year)
        (
            Date(2020, 3, 1),
            Period(0, 0, -1),
            Date(2020, 2, 29),
        ),  # Mar 1 - 1 day = Feb 29 (leap year)
        (
            Date(2021, 3, 1),
            Period(0, 0, -1),
            Date(2021, 2, 28),
        ),  # Mar 1 - 1 day = Feb 28 (non-leap year)
        # Large month additions
        (
            Date(2020, 1, 15),
            Period(0, 12, 0),
            Date(2021, 1, 15),
        ),  # Jan 15 + 12 months = Jan 15 next year
        (
            Date(2020, 1, 15),
            Period(0, 24, 0),
            Date(2022, 1, 15),
        ),  # Jan 15 + 24 months = Jan 15 year after next
        (
            Date(2020, 2, 29),
            Period(0, 12, 0),
            Date(2021, 2, 28),
        ),  # Feb 29 + 12 months = Feb 28 next year (non-leap)
        (
            Date(2020, 2, 29),
            Period(0, 48, 0),
            Date(2024, 2, 29),
        ),  # Feb 29 + 48 months = Feb 29 in 4 years (leap year)
        (
            Date(2020, 1, 15),
            Period(0, 120, 0),
            Date(2030, 1, 15),
        ),  # 120 months = 10 years
        # Large year additions
        (
            Date(2020, 6, 15),
            Period(1, 0, 0),
            Date(2021, 6, 15),
        ),  # Jun 15 + 1 year = Jun 15 next year
        (
            Date(2020, 6, 15),
            Period(4, 0, 0),
            Date(2024, 6, 15),
        ),  # Jun 15 + 4 years = Jun 15 in 4 years
        (
            Date(2020, 2, 29),
            Period(1, 0, 0),
            Date(2021, 2, 28),
        ),  # Feb 29 + 1 year = Feb 28 next year (non-leap)
        (
            Date(2020, 2, 29),
            Period(4, 0, 0),
            Date(2024, 2, 29),
        ),  # Feb 29 + 4 years = Feb 29 in 4 years (leap year)
        (
            Date(2020, 6, 15),
            Period(80, 0, 0),
            Date(2100, 6, 15),
        ),  # 80 years (max within range)
        # Complex mixed cases
        (
            Date(2020, 1, 31),
            Period(1, 1, 1),
            Date(2021, 3, 1),
        ),  # Jan 31 + 1y1m1d = Mar 1 next year
        (
            Date(2020, 2, 29),
            Period(1, 1, 1),
            Date(2021, 3, 30),
        ),  # Feb 29 + 1y1m1d = Mar 30 next year
        (
            Date(2020, 12, 31),
            Period(0, 0, 32),
            Date(2021, 2, 1),
        ),  # Dec 31 + 32 days = Feb 1 next year
        (
            Date(2020, 12, 31),
            Period(0, 0, 62),
            Date(2021, 3, 3),
        ),  # Dec 31 + 62 days = Mar 3 next year
        # Negative period edge cases
        (
            Date(2020, 1, 1),
            Period(0, 0, -1),
            Date(2019, 12, 31),
        ),  # Jan 1 - 1 day = Dec 31 prev year
        (
            Date(2020, 1, 1),
            Period(0, 0, -32),
            Date(2019, 11, 30),
        ),  # Jan 1 - 32 days = Nov 30 prev year
        (
            Date(2020, 3, 1),
            Period(0, -1, 0),
            Date(2020, 2, 1),
        ),  # Mar 1 - 1 month = Feb 1
        (
            Date(2020, 3, 1),
            Period(0, -2, 0),
            Date(2020, 1, 1),
        ),  # Mar 1 - 2 months = Jan 1
        (
            Date(2020, 3, 1),
            Period(-1, 0, 0),
            Date(2019, 3, 1),
        ),  # Mar 1 - 1 year = Mar 1 prev year
        (
            Date(2020, 2, 29),
            Period(-1, 0, 0),
            Date(2019, 2, 28),
        ),  # Feb 29 - 1 year = Feb 28 prev year (non-leap)
        # Edge cases around month boundaries with days
        (Date(2020, 1, 30), Period(0, 1, 1), Date(2020, 3, 1)),
        (Date(2021, 1, 30), Period(0, 1, 1), Date(2021, 3, 1)),
        (Date(2020, 4, 30), Period(0, 1, 1), Date(2020, 5, 31)),
        (Date(2020, 5, 31), Period(0, 1, 1), Date(2020, 7, 1)),
        # Additional edge cases for comprehensive coverage
        # Year jumps across leap years
        (
            Date(2020, 2, 29),
            Period(1, 0, 0),
            Date(2021, 2, 28),
        ),  # Feb 29 + 1 year = Feb 28 (non-leap)
        (
            Date(2024, 2, 29),
            Period(1, 0, 0),
            Date(2025, 2, 28),
        ),  # Feb 29 + 1 year = Feb 28 (non-leap)
        (
            Date(2020, 2, 29),
            Period(4, 0, 0),
            Date(2024, 2, 29),
        ),  # Feb 29 + 4 years = Feb 29 (leap)
        (
            Date(2020, 2, 29),
            Period(2, 0, 0),
            Date(2022, 2, 28),
        ),  # Feb 29 + 2 years = Feb 28 (non-leap)
        (
            Date(2020, 2, 29),
            Period(3, 0, 0),
            Date(2023, 2, 28),
        ),  # Feb 29 + 3 years = Feb 28 (non-leap)
        (
            Date(2020, 2, 29),
            Period(5, 0, 0),
            Date(2025, 2, 28),
        ),  # Feb 29 + 5 years = Feb 28 (non-leap)
        (
            Date(2020, 2, 29),
            Period(8, 0, 0),
            Date(2028, 2, 29),
        ),  # Feb 29 + 8 years = Feb 29 (leap)
        # Month jumps with varying lengths - comprehensive coverage
        (
            Date(2020, 1, 31),
            Period(0, 1, 0),
            Date(2020, 2, 29),
        ),  # Jan 31 + 1 month = Feb 29 (leap)
        (
            Date(2021, 1, 31),
            Period(0, 1, 0),
            Date(2021, 2, 28),
        ),  # Jan 31 + 1 month = Feb 28 (non-leap)
        (
            Date(2020, 1, 31),
            Period(0, 2, 0),
            Date(2020, 3, 31),
        ),  # Jan 31 + 2 months = Mar 31
        (
            Date(2020, 1, 31),
            Period(0, 3, 0),
            Date(2020, 4, 30),
        ),  # Jan 31 + 3 months = Apr 30
        (
            Date(2020, 1, 31),
            Period(0, 12, 0),
            Date(2021, 1, 31),
        ),  # Jan 31 + 12 months = Jan 31 next year
        # Four-year cycle math for leap years
        (Date(2020, 2, 29), Period(1, 0, 0), Date(2021, 2, 28)),  # +1 year
        (Date(2020, 2, 29), Period(2, 0, 0), Date(2022, 2, 28)),  # +2 years
        (Date(2020, 2, 29), Period(3, 0, 0), Date(2023, 2, 28)),  # +3 years
        (Date(2020, 2, 29), Period(4, 0, 0), Date(2024, 2, 29)),  # +4 years (leap year)
        (Date(2020, 2, 29), Period(5, 0, 0), Date(2025, 2, 28)),  # +5 years
        (Date(2020, 2, 29), Period(8, 0, 0), Date(2028, 2, 29)),  # +8 years (leap year)
        # Month lookup path validation - all months with max days
        (
            Date(2020, 1, 31),
            Period(0, 1, 0),
            Date(2020, 2, 29),
        ),  # Jan 31 + 1 month = Feb 29
        (
            Date(2020, 2, 29),
            Period(0, 1, 0),
            Date(2020, 3, 29),
        ),  # Feb 29 + 1 month = Mar 29
        (
            Date(2020, 3, 31),
            Period(0, 1, 0),
            Date(2020, 4, 30),
        ),  # Mar 31 + 1 month = Apr 30
        (
            Date(2020, 4, 30),
            Period(0, 1, 0),
            Date(2020, 5, 30),
        ),  # Apr 30 + 1 month = May 30
        (
            Date(2020, 5, 31),
            Period(0, 1, 0),
            Date(2020, 6, 30),
        ),  # May 31 + 1 month = Jun 30
        (
            Date(2020, 6, 30),
            Period(0, 1, 0),
            Date(2020, 7, 30),
        ),  # Jun 30 + 1 month = Jul 30
        (
            Date(2020, 7, 31),
            Period(0, 1, 0),
            Date(2020, 8, 31),
        ),  # Jul 31 + 1 month = Aug 31
        (
            Date(2020, 8, 31),
            Period(0, 1, 0),
            Date(2020, 9, 30),
        ),  # Aug 31 + 1 month = Sep 30
        (
            Date(2020, 9, 30),
            Period(0, 1, 0),
            Date(2020, 10, 30),
        ),  # Sep 30 + 1 month = Oct 30
        (
            Date(2020, 10, 31),
            Period(0, 1, 0),
            Date(2020, 11, 30),
        ),  # Oct 31 + 1 month = Nov 30
        (
            Date(2020, 11, 30),
            Period(0, 1, 0),
            Date(2020, 12, 30),
        ),  # Nov 30 + 1 month = Dec 30
        (
            Date(2020, 12, 31),
            Period(0, 1, 0),
            Date(2021, 1, 31),
        ),  # Dec 31 + 1 month = Jan 31
    ]


def python_date_plus(base: Date, per: Period) -> Date:
    """Compute base + period using Python's datetime + relativedelta."""
    py_base = base.to_python_date()
    py_res = py_base + relativedelta(years=per.years, months=per.months, days=per.days)
    # Constrain to supported domain if needed; tests stay within range
    return Date.from_python_date(py_res)


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
def test_baseline_equals_ground_truth(base: Date, per: Period, expect: Date):
    sb = BaselineSolver()
    xb = sb.add_date_var("x")
    yb = sb.add_date_var("y")
    sb.add_constraint(xb == base)
    sb.add_constraint(yb == xb + per)
    rb = sb.solve()
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
@pytest.mark.advanced
def test_advanced_equals_ground_truth(base: Date, per: Period, expect: Date):
    sa = AdvancedDateSolver()
    xa = sa.add_date_var("x")
    ya = sa.add_date_var("y")
    sa.add_constraint(xa == base)
    sa.add_constraint(ya == xa + per)
    ra = sa.solve()
    assert ra["status"] == "sat"
    got_a = ra["dates"]["y"]
    assert got_a == expect, f"Advanced: {base} + {per} -> {got_a}, expected {expect}"


@pytest.mark.parametrize(
    "base,per,expect",
    [
        pytest.param(base, per, expect, id=f"solvers_truth_{base}+{per}={expect}")
        for base, per, expect in get_period_arithmetic_test_cases()
    ],
)
@pytest.mark.hybrid
def test_hybrid_equals_ground_truth(base: Date, per: Period, expect: Date):
    sh = HybridDateSolver()
    xh = sh.new_date("x")
    yh = sh.new_date("y")
    sh.add_constraint(xh == base)
    sh.add_constraint(yh == xh + per)
    rh = sh.solve()
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
@pytest.mark.ab
def test_ab_equals_ground_truth(base: Date, per: Period, expect: Date):
    sa = AbDateSolver()
    xa = sa.add_date_var("x")
    ya = sa.add_date_var("y")
    sa.add_constraint(xa == base)
    sa.add_constraint(ya == xa + per)
    ra = sa.solve()
    assert ra["status"] == "sat"
    got_a = ra["dates"]["y"]
    assert got_a == expect, f"AB: {base} + {per} -> {got_a}, expected {expect}"
