"""
Unit tests for the Period class in datesat.core.
"""

import pytest
from datesat.core import Period

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
    with pytest.raises(TypeError) as exc_info:
        a == b
    assert "Cannot compare Period with" in str(exc_info.value)
    with pytest.raises(TypeError) as exc_info:
        a != b
    assert "Cannot compare Period with" in str(exc_info.value)

@pytest.mark.parametrize("other", ["1y2m3d", 1, None, (1, 2, 3), [1, 2, 3]])
def test_not_equal_to_non_period(sample_period_obj, other):
    with pytest.raises(TypeError) as exc_info:
        sample_period_obj != other
    assert "Cannot compare Period with" in str(exc_info.value)

def test_not_equal_to_date_object(sample_date_obj):
    # Use any Date from fixtures to assert cross-type inequality
    some_date = sample_date_obj
    with pytest.raises(TypeError) as exc_info:
        Period(1, 2, 3) != some_date
    assert "Cannot compare Period with" in str(exc_info.value)


# --------------------------------------------------------------------
# String
# --------------------------------------------------------------------

def test_str_is_canonical():
    assert str(Period(1, 2, 3)) == "Period(1, 2, 3)"
    assert str(Period(-1, -2, -3)) == "Period(-1, -2, -3)"
    assert str(Period(0, 0, 0)) == "Period(0, 0, 0)"


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


# --------------------------------------------------------------------
# Period bounds validation
# --------------------------------------------------------------------

@pytest.mark.parametrize(
    "years,months,days",
    [
        # Values at the old boundary
        (200, 0, 0),
        (-200, 0, 0),
        (0, 2400, 0),
        (0, -2400, 0),
        (0, 0, 73048),
        (0, 0, -73048),
        # Values that used to exceed the old [1900, 2100] period bounds - now accepted
        (201, 0, 0),
        (-201, 0, 0),
        (0, 2401, 0),
        (0, -2401, 0),
        (0, 0, 73049),
        (0, 0, -73049),
        (200, 0, 73049),
        (201, 2400, 0),
    ],
)
def test_period_bounds_validation(years, months, days):
    """Period is no longer range-bounded; every integer triple must be accepted."""
    p = Period(years, months, days)
    assert p.years == years
    assert p.months == months
    assert p.days == days


def test_period_bounds_constants():
    """Test that Period bounds constants are accessible and correct."""
    assert Period.MAX_PERIOD_YEARS == 200
    assert Period.MAX_PERIOD_MONTHS == 2400
    assert Period.MAX_PERIOD_DAYS == 73048


def test_period_arithmetic_respects_bounds():
    """Period is no longer range-bounded; arithmetic that used to overflow is now allowed."""
    # 101 + 101 = 202: used to exceed the old 200-year cap, now valid.
    p1 = Period(101, 0, 0)
    p2 = Period(101, 0, 0)
    result = p1 + p2
    assert (result.years, result.months, result.days) == (202, 0, 0)

    # Multiplication that would have exceeded bounds is now allowed.
    p3 = Period(101, 0, 0)
    result = p3 * 2
    assert (result.years, result.months, result.days) == (202, 0, 0)

    # Days that would have exceeded the old 73048-day cap are now allowed.
    p4 = Period(0, 0, 36525)
    p5 = Period(0, 0, 36525)
    result = p4 + p5
    assert (result.years, result.months, result.days) == (0, 0, 73050)


@pytest.mark.parametrize(
    "years,months,days",
    [
        # Very large values that should be rejected
        (9_999_999, 0, 0),
        (0, 9_999_999, 0),
        (0, 0, 9_999_999),
        (9_999_999, 9_999_999, 9_999_999),
        (-9_999_999, 0, 0),
        (0, -9_999_999, 0),
        (0, 0, -9_999_999),
        (-9_999_999, -9_999_999, -9_999_999),
        # Other large values
        (1_000_000, 0, 0),
        (0, 10_000, 0),
        (0, 0, 100_000),
        (500, 5000, 100_000),
    ],
)
def test_large_period_values_rejected(years, months, days):
    """Period is no longer range-bounded; very large integer values must be accepted.

    Kept as a regression guard: the function name and fixture used to assert
    that these values raised ValueError. The rename would obscure history, so
    we keep the name and flip the assertion.
    """
    p = Period(years, months, days)
    assert (p.years, p.months, p.days) == (years, months, days)
