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
