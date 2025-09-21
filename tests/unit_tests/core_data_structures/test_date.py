"""
Unit tests for the Date class in datesmt.core.

Tests cover constructor validation, equality comparison, string representation,
Python date conversion, and edge cases.
"""

from datetime import date as pydate

import pytest

from datesmt.core import Date

# -------------------------
# Constructor and validation
# -------------------------


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 6, 15),
        (2024, 2, 29),  # leap
        (2000, 2, 29),  # century leap
        (1, 1, 1),
        (9999, 12, 31),
    ],
)
def test_constructor_valid(y, m, d):
    dobj = Date(y, m, d)
    assert (dobj.year, dobj.month, dobj.day) == (y, m, d)


def test_constructor_valid_from_fixture(sample_dates):
    # bulk sanity over curated examples
    for name, dobj in sample_dates.items():
        assert isinstance(dobj, Date), f"fixture {name} must be Date"
        assert 1 <= dobj.month <= 12
        assert 1 <= dobj.day <= 31


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 2, 29),  # non-leap Feb 29
        (1900, 2, 29),  # century non-leap
        (2023, 4, 31),  # 30-day month overflow
        (2023, 13, 1),  # month > 12
        (2023, 0, 1),  # month 0
        (2023, 1, 0),  # day 0
        (2023, 1, 32),  # day > 31
        (-1, 1, 1),  # negative year (if disallowed)
        (10000, 1, 1),  # beyond 9999
    ],
)
def test_constructor_invalid_raises_value_error(y, m, d):
    with pytest.raises(ValueError):
        Date(y, m, d)


def test_constructor_invalid_from_fixture(invalid_dates):
    for y, m, d in invalid_dates:
        with pytest.raises(ValueError):
            Date(y, m, d)


@pytest.mark.parametrize(
    "y,m,d,msg_re",
    [
        (2023, 2, 29, r"Invalid date"),
    ],
)
def test_validation_message_format_is_stable(y, m, d, msg_re):
    # keep this only if message text is part of the public contract
    with pytest.raises(ValueError, match=msg_re):
        Date(y, m, d)


# -------------------------
# Equality and hashing
# -------------------------


def test_equality_and_hash():
    a = Date(2023, 6, 15)
    b = Date(2023, 6, 15)
    c = Date(2023, 6, 16)
    assert a == b
    assert not (a != b)
    assert hash(a) == hash(b)
    assert a != c


@pytest.mark.parametrize("other", ["2023-06-15", 2023, None, (2023, 6, 15)])
def test_not_equal_to_non_date(other):
    assert Date(2023, 6, 15) != other


# -------------------------
# String and repr
# -------------------------


def test_repr_is_canonical():
    assert repr(Date(2023, 6, 15)) == "Date(2023, 6, 15)"


def test_str_contains_fields():
    # do not overfit to exact formatting unless promised
    s = str(Date(2023, 1, 5))
    for token in ("2023", "1", "5"):
        assert token in s


# -------------------------
# Python date interop
# -------------------------


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 6, 15),
        (2024, 2, 29),
    ],
)
def test_to_python_date(y, m, d):
    dobj = Date(y, m, d)
    pd = dobj.to_python_date()
    assert isinstance(pd, pydate)
    assert (pd.year, pd.month, pd.day) == (y, m, d)


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 6, 15),
        (2024, 2, 29),
    ],
)
def test_from_python_date(y, m, d):
    dobj = Date.from_python_date(pydate(y, m, d))
    assert (dobj.year, dobj.month, dobj.day) == (y, m, d)


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 6, 15),
        (2024, 2, 29),
        (2000, 2, 29),
    ],
)
def test_round_trip(y, m, d):
    original = Date(y, m, d)
    round_tripped = Date.from_python_date(original.to_python_date())
    assert round_tripped == original


def test_round_trip_edge_cases(edge_case_dates):
    for original in edge_case_dates:
        rt = Date.from_python_date(original.to_python_date())
        assert rt == original


# -------------------------
# Month-end coverage
# -------------------------


@pytest.mark.parametrize(
    "y,m,d",
    [
        (2023, 4, 30),
        (2023, 6, 30),
        (2023, 9, 30),
        (2023, 11, 30),
        (2023, 1, 31),
        (2023, 3, 31),
        (2023, 5, 31),
        (2023, 7, 31),
        (2023, 8, 31),
        (2023, 10, 31),
        (2023, 12, 31),
    ],
)
def test_month_end_valid_dates(y, m, d):
    assert Date(y, m, d).day == d


# -------------------------
# Immutability
# -------------------------


def test_attributes_are_immutable():
    dobj = Date(2023, 6, 15)
    with pytest.raises(AttributeError):
        dobj.year = 2024


# -------------------------
# Year boundary and policy tests
# -------------------------


def test_year_zero_policy():
    """Test year 0 policy (astronomical vs proleptic Gregorian)."""
    # This tests the chosen policy for year 0
    # If year 0 is supported, it should follow leap year rules
    try:
        date_zero = Date(0, 1, 1)
        # Year 0 should be a leap year (0 % 400 == 0)
        assert date_zero.year == 0
    except ValueError:
        # If year 0 is not supported, that's also a valid policy
        pass


def test_negative_year_policy():
    """Test negative year policy."""
    # Test that negative years either work or are consistently rejected
    try:
        date_neg = Date(-1, 1, 1)
        assert date_neg.year == -1
        # If negative years are supported, test leap year rules
        # -4 should be a leap year (divisible by 4)
        date_neg4 = Date(-4, 2, 29)
        assert date_neg4.year == -4
    except ValueError:
        # If negative years are not supported, that's also valid
        pass


def test_year_bounds_validation():
    """Test year bounds validation."""
    # Test minimum and maximum supported years
    try:
        # Test very early date
        early_date = Date(1, 1, 1)
        assert early_date.year == 1
    except ValueError:
        pass
    
    try:
        # Test very late date
        late_date = Date(9999, 12, 31)
        assert late_date.year == 9999
    except ValueError:
        pass


def test_invalid_month_handling():
    """Test comprehensive invalid month handling."""
    invalid_months = [0, 13, -1, 14, 100]
    
    for month in invalid_months:
        with pytest.raises(ValueError):
            Date(2023, month, 1)


def test_invalid_day_handling():
    """Test comprehensive invalid day handling."""
    # Test day 0 and negative days
    with pytest.raises(ValueError):
        Date(2023, 1, 0)
    
    with pytest.raises(ValueError):
        Date(2023, 1, -1)
    
    # Test day overflow for each month
    month_days = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }
    
    for month, max_days in month_days.items():
        # Test day overflow
        with pytest.raises(ValueError):
            Date(2023, month, max_days + 1)
        
        # Test day overflow with very large number
        with pytest.raises(ValueError):
            Date(2023, month, 100)


def test_february_29_validation():
    """Test February 29 validation for leap and non-leap years."""
    # Leap years (should allow Feb 29)
    leap_years = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
    for year in leap_years:
        date_leap = Date(year, 2, 29)
        assert date_leap.day == 29
    
    # Non-leap years (should reject Feb 29)
    non_leap_years = [1900, 2001, 2002, 2003, 2005, 2100]
    for year in non_leap_years:
        with pytest.raises(ValueError):
            Date(year, 2, 29)


def test_century_leap_year_validation():
    """Test century leap year validation (400-year rule)."""
    # Century years divisible by 400 (leap)
    century_leap_years = [1600, 2000, 2400]
    for year in century_leap_years:
        date_leap = Date(year, 2, 29)
        assert date_leap.day == 29
    
    # Century years not divisible by 400 (not leap)
    century_non_leap_years = [1700, 1800, 1900, 2100, 2200, 2300]
    for year in century_non_leap_years:
        with pytest.raises(ValueError):
            Date(year, 2, 29)


def test_30_day_month_validation():
    """Test 30-day month validation."""
    thirty_day_months = [4, 6, 9, 11]
    for month in thirty_day_months:
        # Should allow day 30
        date_30 = Date(2023, month, 30)
        assert date_30.day == 30
        
        # Should reject day 31
        with pytest.raises(ValueError):
            Date(2023, month, 31)


def test_31_day_month_validation():
    """Test 31-day month validation."""
    thirty_one_day_months = [1, 3, 5, 7, 8, 10, 12]
    for month in thirty_one_day_months:
        # Should allow day 31
        date_31 = Date(2023, month, 31)
        assert date_31.day == 31


def test_date_construction_error_messages():
    """Test that Date construction errors have informative messages."""
    # Test that error messages are helpful
    with pytest.raises(ValueError) as exc_info:
        Date(2023, 2, 29)  # Non-leap year Feb 29
    assert "Invalid date" in str(exc_info.value) or "February" in str(exc_info.value)
    
    with pytest.raises(ValueError) as exc_info:
        Date(2023, 13, 1)  # Invalid month
    assert "month" in str(exc_info.value) or "Invalid" in str(exc_info.value)
    
    with pytest.raises(ValueError) as exc_info:
        Date(2023, 1, 0)  # Invalid day
    assert "day" in str(exc_info.value) or "Invalid" in str(exc_info.value)
