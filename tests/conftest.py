"""
Pytest configuration and shared fixtures for DATE-SMT tests.
"""

import os
import sys
from datetime import date, timedelta

import pytest

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datesmt.core import Date, Period

# --------------------------------------------------------------------
# Date fixtures
# --------------------------------------------------------------------


# Parametrized equivalents for single-case tests
@pytest.fixture(
    params=[
        Date(2023, 6, 15),
        Date(2024, 2, 29),
        Date(2000, 12, 31),
        Date(1900, 3, 1),
        Date(2100, 2, 28),
        Date(2023, 4, 30),
        Date(2023, 1, 1),
        Date(2023, 12, 31),
    ]
)
def sample_date_obj(request):
    return request.param


@pytest.fixture(
    params=[
        (2023, 2, 29),  # Feb 29 in non-leap year
        (2023, 4, 31),  # April 31
        (2023, 13, 1),  # Month 13
        (2023, 1, 32),  # Day 32
        (2023, 2, 30),  # Feb 30
        (2023, 2, 31),  # Feb 31
        (-2000, 2, 29),  # Negative year
        (-2000, 13, 1),  # Month 13
        (2000, -1, 1),  # Negative month
        (2001, 1, -5),  # Negative day
    ]
)
def invalid_date_tuple(request):
    return request.param


@pytest.fixture(params=[0, 13, -1, 14, 100, -2000])
def invalid_month_val(request):
    return request.param


@pytest.fixture(
    params=[
        (None, None, None),
        (True, False, True),
        (2023, 2, "15"),
        ("2023", "6", "15"),
        (2011, 2, [3]),
        (2011, 2, {3}),
        (2021, 3, {3: 4}),
        (2011, 2, None),
        (2001, 2),
        (2003),
    ]
)
def invalid_date_format_tuple(request):
    return request.param


@pytest.fixture
def leap_years():
    """Leap year test data."""
    return {
        'leap_years': [2000, 2004, 2008, 2012, 2016, 2020, 2024],
        'non_leap_years': [1900, 2001, 2002, 2003, 2005, 2100],
        'century_leap': [2000],
        'century_non_leap': [1900, 2100],
    }


@pytest.fixture(params=[2000, 2004, 2008, 2012, 2016, 2020, 2024])
def leap_year_year(request):
    return request.param


@pytest.fixture(params=[1900, 2001, 2002, 2003, 2005, 2100])
def non_leap_year_year(request):
    return request.param


@pytest.fixture
def days_in_month_data():
    """Test data for days in month calculation."""
    return {
        'regular_months': {
            1: 31,  # January
            3: 31,  # March
            4: 30,  # April
            5: 31,  # May
            6: 30,  # June
            7: 31,  # July
            8: 31,  # August
            9: 30,  # September
            10: 31,  # October
            11: 30,  # November
            12: 31,  # December
        },
        'february_leap': 29,
        'february_non_leap': 28,
    }


@pytest.fixture(
    params=[
        (1, 31),
        (2, 28),
        (3, 31),
        (4, 30),
        (5, 31),
        (6, 30),
        (7, 31),
        (8, 31),
        (9, 30),
        (10, 31),
        (11, 30),
        (12, 31),
    ]
)
def month_max_day_entry(request):
    return request.param


@pytest.fixture(params=[4, 6, 9, 11])
def thirty_day_month(request):
    return request.param


@pytest.fixture(params=[1, 3, 5, 7, 8, 10, 12])
def thirty_one_day_month(request):
    return request.param


@pytest.fixture(
    params=[
        # Triplets: (a, b==a, c!=a)
        (Date(2023, 6, 15), Date(2023, 6, 15), Date(2023, 6, 16)),
        (Date(1900, 3, 1), Date(1900, 3, 1), Date(1900, 3, 2)),
    ]
)
def equality_triplet(request):
    return request.param


@pytest.fixture(
    params=[
        # 31-day months in 2023
        (2023, 1, 31),
        (2023, 3, 31),
        (2023, 5, 31),
        (2023, 7, 31),
        (2023, 8, 31),
        (2023, 10, 31),
        (2023, 12, 31),
        # 30-day months in 2023
        (2023, 4, 30),
        (2023, 6, 30),
        (2023, 9, 30),
        (2023, 11, 30),
        # February ends for non-leap and leap years
        (2023, 2, 28),
        (2024, 2, 29),
    ]
)
def month_end_date(request):
    return request.param


@pytest.fixture(
    params=[
        date(2023, 6, 15),
        date(2024, 2, 29),
        date(2000, 12, 31),
        date(1900, 3, 1),
        date(2100, 2, 28),
    ]
)
def python_date_obj(request):
    return request.param


@pytest.fixture(
    params=[
        Date(1900, 3, 1),  # Min allowed boundary
        Date(2100, 2, 28),  # Max allowed boundary
        Date(2023, 1, 1),  # Year start
        Date(2023, 12, 31),  # Year end
        Date(2023, 2, 28),  # Feb 28 (non-leap)
        Date(2024, 2, 29),  # Feb 29 (leap)
    ]
)
def edge_case_date(request):
    return request.param


@pytest.fixture(
    params=[
        (1600, 2, 29),
        (2400, 4, 30),
        (1900, 2, 28),
        (2100, 3, 1),
        (2102, 2, 28),
    ]
)
def out_of_range_date_tuple(request):
    return request.param


# --------------------------------------------------------------------
# Period fixtures
# --------------------------------------------------------------------


@pytest.fixture(
    params=[
        Period(0, 0, 0),
        Period(0, 0, 1),
        Period(0, 1, 0),
        Period(1, 0, 0),
        Period(1, 2, 3),
        Period(-1, -2, -3),
        Period(10, 6, 15),
        Period(1, -2, 3),  # mixed signs
        Period(100, 50, 365),
        Period(200, 0, 0),  # Max years (boundary)
        Period(0, 2400, 0),  # Max months (boundary)
        Period(0, 0, 73048),  # Max days (boundary)
    ]
)
def sample_period_obj(request):
    return request.param


@pytest.fixture(
    params=[
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (1, 0, 0),
        (1, 2, 3),
        (-1, -2, -3),
        (1, -2, 3),  # mixed signs
        (10, 6, 15),
        (100, 50, 365),
        (200, 0, 0),  # Max years (boundary)
        (0, 2400, 0),  # Max months (boundary)
        (0, 0, 73048),  # Max days (boundary)
    ]
)
def sample_period_tuple(request):
    return request.param


@pytest.fixture(
    params=[
        (0, 1.5, 0),  # float
        (1.4, 0, 0),  # float
        (1.9, 2.9, 3.9),  # floats
        (-1 / 4, -2 / 3, -3 / 4),  # fractions
        (None, None, None),
        (True, False, True),  # bools
        (1, 2, "3"),  # str in slot
        ("1", "2", "3"),  # all str
        (1, 2, [3]),  # list
        (1, 2, {3}),  # set
        (1, 2, {3: 4}),  # dict
        (1, 2, None),  # None in slot
        (32, 0),  # wrong arity (2-tuple)
        (32,),  # wrong arity (1-tuple)
    ]
)
def invalid_period_format_tuple(request):
    return request.param


# Autouse session fixture to import all modules under `datesmt_int` so coverage includes files
import importlib
import pkgutil


@pytest.fixture(autouse=True, scope="session")
def _import_all_datesmt_modules():
    try:
        pkg = importlib.import_module("datesmt_int")
        if hasattr(pkg, "__path__"):
            for _, name, _ in pkgutil.walk_packages(
                pkg.__path__, prefix="datesmt_int."
            ):
                try:
                    importlib.import_module(name)
                except Exception:
                    # Ignore optional or platform-specific modules that may fail to import
                    pass
    except Exception:
        # If the root package itself fails to import, let tests proceed; failures will surface elsewhere
        pass


# Ensure general core_data_structures tests run under any solver mark filter
def pytest_collection_modifyitems(config, items):
    try:
        import pytest  # noqa: F401
    except Exception:
        return

    for item in items:
        fspath = str(getattr(item, "fspath", ""))
        if (
            "/tests/unit_tests/core_data_structures/" in fspath
            or fspath.endswith("tests/unit_tests/core_data_structures/test_date.py")
            or fspath.endswith("tests/unit_tests/core_data_structures/test_period.py")
        ):
            item.add_marker("baseline")
            item.add_marker("epoch_days")
            item.add_marker("hybrid")
            item.add_marker("alpha_beta")
            item.add_marker("alpha_beta_table")
