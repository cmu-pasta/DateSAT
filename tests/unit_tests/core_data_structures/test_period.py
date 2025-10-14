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


def test_constructor_assigns_fields(sample_period_tuple):
    y, m, d = sample_period_tuple
    p = Period(y, m, d)
    assert (p.years, p.months, p.days) == (y, m, d)


def test_constructor_from_fixture(sample_period_obj):
    # Bulk sanity across curated examples
    p = sample_period_obj
    assert isinstance(p, Period)


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
def test_not_equal_to_non_period(sample_period_obj, other):
    assert sample_period_obj != other


def test_not_equal_to_date_object(sample_date_obj):
    # Use any Date from fixtures to assert cross-type inequality
    some_date = sample_date_obj
    assert Period(1, 2, 3) != some_date


# --------------------------------------------------------------------
# String / repr
# --------------------------------------------------------------------


def test_repr_is_canonical():
    assert repr(Period(1, 2, 3)) == "Period(1, 2, 3)"
    assert repr(Period(-1, -2, -3)) == "Period(-1, -2, -3)"
    assert repr(Period(0, 0, 0)) == "Period(0, 0, 0)"


def test_str_contains_components_without_overfitting(sample_period_obj):
    # Avoid overspecifying exact format unless it's a public contract
    p = sample_period_obj
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


# --------------------------------------------------------------------
# Invalid input handling
# --------------------------------------------------------------------


def test_invalid_input_handling(invalid_period_format_tuple):
    args = invalid_period_format_tuple
    # Wrong arity should raise TypeError (constructor signature mismatch)
    if not isinstance(args, tuple) or len(args) != 3:
        with pytest.raises(TypeError):
            Period(*args)
        return
    y, m, d = args
    # Non-int (or bool) components should raise ValueError per Period validation
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (y, m, d)):
        with pytest.raises(ValueError):
            Period(y, m, d)
    else:
        # This fixture is intended to contain only invalid cases; reaching here
        # means a valid triple slipped into the invalid set.
        pytest.fail(f"invalid_period_format_tuple contains valid input: {(y, m, d)}")
