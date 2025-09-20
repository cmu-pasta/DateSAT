"""
Pytest configuration and shared fixtures for DATE-SMT tests.
"""

from datetime import date, timedelta

import pytest

from datesmt.core import Date, Period


@pytest.fixture
def sample_dates():
    """Sample Date objects for testing."""
    return {
        'normal_date': Date(2023, 6, 15),
        'leap_year_date': Date(2024, 2, 29),
        'century_date': Date(2000, 12, 31),
        'early_date': Date(1900, 1, 1),
        'future_date': Date(2100, 6, 15),
        'month_end': Date(2023, 4, 30),
        'year_start': Date(2023, 1, 1),
        'year_end': Date(2023, 12, 31),
    }


@pytest.fixture
def sample_periods():
    """Sample Period objects for testing."""
    return {
        'zero_period': Period(0, 0, 0),
        'one_day': Period(0, 0, 1),
        'one_month': Period(0, 1, 0),
        'one_year': Period(1, 0, 0),
        'mixed_period': Period(1, 2, 3),
        'negative_period': Period(-1, -2, -3),
        'large_period': Period(10, 6, 15),
    }


@pytest.fixture
def invalid_dates():
    """Invalid date data for testing error conditions."""
    return [
        (2023, 2, 29),  # Feb 29 in non-leap year
        (2023, 4, 31),  # April 31
        (2023, 13, 1),  # Month 13
        (2023, 0, 1),  # Month 0
        (2023, 1, 0),  # Day 0
        (2023, 1, 32),  # Day 32
        (2023, 2, 30),  # Feb 30
        (2023, 2, 31),  # Feb 31
    ]


@pytest.fixture
def leap_years():
    """Leap year test data."""
    return {
        'leap_years': [2000, 2004, 2008, 2012, 2016, 2020, 2024],
        'non_leap_years': [1900, 2001, 2002, 2003, 2005, 2100],
        'century_leap': [1600, 2000, 2400],
        'century_non_leap': [1700, 1800, 1900, 2100, 2200, 2300],
    }


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


@pytest.fixture
def python_dates():
    """Python date objects for conversion testing."""
    return [
        date(2023, 6, 15),
        date(2024, 2, 29),
        date(2000, 12, 31),
        date(1900, 1, 1),
        date(2100, 6, 15),
    ]


@pytest.fixture
def edge_case_dates():
    """Edge case dates for boundary testing."""
    return [
        Date(1, 1, 1),  # Year 1
        Date(9999, 12, 31),  # Year 9999
        Date(2023, 1, 1),  # Year start
        Date(2023, 12, 31),  # Year end
        Date(2023, 2, 28),  # Feb 28 (non-leap)
        Date(2024, 2, 29),  # Feb 29 (leap)
    ]
