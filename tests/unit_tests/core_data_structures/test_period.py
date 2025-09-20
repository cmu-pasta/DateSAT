"""
Unit tests for the Period class in datesmt.core.

Tests cover constructor, equality comparison, string/repr,
immutability, and property-based sanity checks.
"""

import pytest

from datesmt.core import Period

# --------------------------------------------------------------------
# Constructor & basic value semantics
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "y,m,d",
    [
        (0, 0, 0),
        (1, 2, 3),
        (-1, -2, -3),
        (1, -2, 3),  # mixed signs
        (100, 50, 365),  # large-ish
    ],
)
def test_constructor_assigns_fields(y, m, d):
    p = Period(y, m, d)
    assert (p.years, p.months, p.days) == (y, m, d)


def test_constructor_from_fixture(sample_periods):
    # Bulk sanity across curated examples
    for name, p in sample_periods.items():
        assert isinstance(p, Period), f"fixture {name} must be Period"


@pytest.mark.parametrize(
    "y,m,d",
    [
        (5, 0, 0),
        (0, 6, 0),
        (0, 0, 30),
    ],
)
def test_constructor_zero_components(y, m, d):
    p = Period(y, m, d)
    assert (p.years, p.months, p.days) == (y, m, d)


# If Period accepts any integers (no validation/normalization), keep this test.
@pytest.mark.parametrize(
    "y,m,d",
    [
        (999_999, 999_999, 999_999),
        (-999_999, -999_999, -999_999),
    ],
)
def test_constructor_accepts_any_ints(y, m, d):
    p = Period(y, m, d)
    assert (p.years, p.months, p.days) == (y, m, d)


# --------------------------------------------------------------------
# Equality & hashing (value semantics)
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected_equal",
    [
        (Period(1, 2, 3), Period(1, 2, 3), True),
        (Period(-1, -2, -3), Period(-1, -2, -3), True),
        (Period(1, 2, 3), Period(1, 2, 4), False),
        (Period(1, 2, 3), Period(2, 2, 3), False),
        (Period(1, 2, 3), Period(1, 3, 3), False),
    ],
)
def test_equality(a, b, expected_equal):
    if expected_equal:
        assert a == b
        assert not (a != b)
        assert hash(a) == hash(b)  # equal objects must have equal hashes
    else:
        assert a != b
        assert not (a == b)


@pytest.mark.parametrize("other", ["1y2m3d", 1, None, (1, 2, 3), [1, 2, 3]])
def test_not_equal_to_non_period(other):
    assert Period(1, 2, 3) != other


def test_not_equal_to_date_object(sample_dates):
    # Use any Date from fixtures to assert cross-type inequality
    some_date = next(iter(sample_dates.values()))
    assert Period(1, 2, 3) != some_date


# --------------------------------------------------------------------
# String / repr
# --------------------------------------------------------------------


def test_repr_is_canonical():
    assert repr(Period(1, 2, 3)) == "Period(1, 2, 3)"
    assert repr(Period(-1, -2, -3)) == "Period(-1, -2, -3)"
    assert repr(Period(0, 0, 0)) == "Period(0, 0, 0)"


def test_str_contains_components_without_overfitting(sample_periods):
    # Avoid overspecifying exact format unless it's a public contract
    for _, p in sample_periods.items():
        s = str(p)
        for token in (str(p.years), str(p.months), str(p.days)):
            assert token in s


# --------------------------------------------------------------------
# Properties / immutability
# --------------------------------------------------------------------


def test_attributes_are_readable():
    p = Period(1, 2, 3)
    assert (p.years, p.months, p.days) == (1, 2, 3)


def test_attributes_are_immutable():
    p = Period(1, 2, 3)
    with pytest.raises(AttributeError):
        p.years = 9
    with pytest.raises(AttributeError):
        p.months = 9
