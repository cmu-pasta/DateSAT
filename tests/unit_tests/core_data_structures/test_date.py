"""
Unit tests for the Date class in datesat.core.
"""

from datetime import date as pydate
import pytest
from datesat.core import Date


# -------------------------
# Constructor and validation
# -------------------------

def test_constructor_valid_from_fixture(sample_date_obj):
    # bulk sanity over curated examples
    dobj = sample_date_obj
    assert isinstance(dobj, Date)
    assert 1 <= dobj.month <= 12
    assert 1 <= dobj.day <= 31

def test_constructor_invalid_from_fixture(invalid_date_tuple):
    y, m, d = invalid_date_tuple
    with pytest.raises(ValueError):
        Date(y, m, d)

def test_constructor_out_of_range_from_fixture(out_of_range_date_tuple):
    y, m, d = out_of_range_date_tuple
    with pytest.raises(ValueError):
        Date(y, m, d)


# -------------------------
# Equality and hashing
# -------------------------

def test_equality_and_hash(equality_triplet):
    a, b, c = equality_triplet
    assert a == b
    assert not (a != b)
    assert hash(a) == hash(b)
    assert a != c

@pytest.mark.parametrize("other", ["2023-06-15", 2023, None, (2023, 6, 15)])
def test_not_equal_to_non_date(sample_date_obj, other):
    a = sample_date_obj
    with pytest.raises(TypeError) as exc_info:
        a != other
    assert "Cannot compare Date with" in str(exc_info.value)


# -------------------------
# String
# -------------------------

def test_str_is_canonical():
    assert str(Date(2023, 6, 15)) == "Date(2023, 6, 15)"

def test_str_contains_fields():
    s = str(Date(2023, 1, 5))
    for token in ("2023", "1", "5"):
        assert token in s


# -------------------------
# Python date interop
# -------------------------

def test_to_python_date(edge_case_date):
    dobj = edge_case_date
    pd = dobj.to_python_date()
    assert isinstance(pd, pydate)
    assert (pd.year, pd.month, pd.day) == (dobj.year, dobj.month, dobj.day)

def test_from_python_date(python_date_obj):
    p = python_date_obj
    dobj = Date.from_python_date(p)
    assert (dobj.year, dobj.month, dobj.day) == (p.year, p.month, p.day)

def test_conversion(edge_case_date):
    original = edge_case_date
    converted = Date.from_python_date(original.to_python_date())
    assert converted == original


# -------------------------
# Month-end coverage
# -------------------------

def test_month_end_valid_dates(month_end_date):
    y, m, d = month_end_date
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

def test_invalid_month_handling(invalid_month_val):
    with pytest.raises(ValueError):
        Date(2023, invalid_month_val, 1)

def test_february_29_allowed_in_leap_year(leap_year_year):
    d = Date(leap_year_year, 2, 29)
    assert d.day == 29

def test_february_29_rejected_in_non_leap_year(non_leap_year_year):
    with pytest.raises(ValueError):
        Date(non_leap_year_year, 2, 29)

def test_century_leap_year_validation():
    # Century years divisible by 400 (leap) — only test within supported range
    # 2000 is within [1900, 2100]; 1600 and 2400 are out of range and should error
    date_leap = Date(2000, 2, 29)
    assert date_leap.day == 29
    for year in [1600, 2400]:
        with pytest.raises(ValueError):
            Date(year, 2, 29)

    # Century years not divisible by 400 (not leap)
    century_non_leap_years = [1700, 1800, 1900, 2100, 2200, 2300]
    for year in century_non_leap_years:
        with pytest.raises(ValueError):
            Date(year, 2, 29)

def test_30_day_month_validation(thirty_day_month):
    month = thirty_day_month
    assert Date(2023, month, 30).day == 30
    with pytest.raises(ValueError):
        Date(2023, month, 31)

def test_31_day_month_validation(thirty_one_day_month):
    month = thirty_one_day_month
    assert Date(2023, month, 31).day == 31

def test_invalid_inrange_error_message(invalid_date_tuple):
    y, m, d = invalid_date_tuple
    with pytest.raises(ValueError) as exc_info:
        Date(y, m, d)
    assert "Invalid date" in str(exc_info.value)

def test_out_of_range_error_message(out_of_range_date_tuple):
    y, m, d = out_of_range_date_tuple
    with pytest.raises(ValueError) as exc_info:
        Date(y, m, d)
    assert "Date outside allowed range" in str(exc_info.value)

def test_invalid_date_input_format(invalid_date_format_tuple):
    args = invalid_date_format_tuple
    # Wrong arity should raise TypeError at call time
    if not isinstance(args, tuple) or len(args) != 3:
        with pytest.raises(TypeError):
            Date(*args)
        return
    y, m, d = args
    # Non-int (or bool) components should raise ValueError per Date validation
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (y, m, d)):
        with pytest.raises(ValueError):
            Date(y, m, d)
    else:
        # This fixture is intended to contain only invalid cases; reaching here
        # means a valid triple slipped into the invalid set.
        pytest.fail(f"invalid_date_format_tuple contains valid input: {(y, m, d)}")
