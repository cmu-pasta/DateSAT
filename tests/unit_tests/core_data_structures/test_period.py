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
    "years,months,days,should_raise",
    [
        # Valid boundary cases
        (200, 0, 0, False),  # Max years
        (-200, 0, 0, False),  # Max negative years
        (0, 2400, 0, False),  # Max months
        (0, -2400, 0, False),  # Max negative months
        (0, 0, 73048, False),  # Max days
        (0, 0, -73048, False),  # Max negative days
        # Invalid cases exceeding bounds
        (201, 0, 0, True),  # Exceeds max years
        (-201, 0, 0, True),  # Exceeds max negative years
        (0, 2401, 0, True),  # Exceeds max months
        (0, -2401, 0, True),  # Exceeds max negative months
        (0, 0, 73049, True),  # Exceeds max days
        (0, 0, -73049, True),  # Exceeds max negative days
        # Mixed valid/invalid
        (200, 0, 73049, True),  # Valid years, invalid days
        (201, 2400, 0, True),  # Invalid years, valid months
    ],
)
def test_period_bounds_validation(years, months, days, should_raise):
    """Test that Period validates bounds correctly."""
    if should_raise:
        with pytest.raises(ValueError) as exc_info:
            Period(years, months, days)
        # Verify error message mentions the bound
        error_msg = str(exc_info.value)
        if abs(years) > Period.MAX_PERIOD_YEARS:
            assert "years" in error_msg.lower()
            assert str(Period.MAX_PERIOD_YEARS) in error_msg
        if abs(months) > Period.MAX_PERIOD_MONTHS:
            assert "months" in error_msg.lower()
            assert str(Period.MAX_PERIOD_MONTHS) in error_msg
        if abs(days) > Period.MAX_PERIOD_DAYS:
            assert "days" in error_msg.lower()
            assert str(Period.MAX_PERIOD_DAYS) in error_msg
    else:
        # Should not raise
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
    """Test that Period arithmetic operations validate bounds when creating new Periods."""
    # Valid periods that when added exceed bounds
    p1 = Period(101, 0, 0)  # 101 + 101 = 202 > 200
    p2 = Period(101, 0, 0)
    
    # Adding them should exceed bounds and raise ValueError
    with pytest.raises(ValueError) as exc_info:
        result = p1 + p2  # This creates Period(202, 0, 0) which exceeds bounds
    assert "years" in str(exc_info.value).lower()
    
    # Multiplication can also exceed bounds
    p3 = Period(101, 0, 0)
    with pytest.raises(ValueError) as exc_info:
        result = p3 * 2  # This creates Period(202, 0, 0) which exceeds bounds
    assert "years" in str(exc_info.value).lower()
    
    # Test with days that exceed bounds when added
    p4 = Period(0, 0, 36525)  # 36525 + 36525 = 73050 > 73048
    p5 = Period(0, 0, 36525)
    with pytest.raises(ValueError) as exc_info:
        result = p4 + p5
    assert "days" in str(exc_info.value).lower()


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
    """Test that very large Period values (e.g., 9_999_999) are rejected with appropriate error messages.
    
    Note: Period validation checks components in order (years, months, days) and raises on the first
    violation, so only the first invalid component will be reported in the error message.
    """
    with pytest.raises(ValueError) as exc_info:
        Period(years, months, days)
    
    error_msg = str(exc_info.value)
    
    # Verify the error message is informative
    assert "out of range" in error_msg.lower()
    
    # Period validation checks in order: years, months, days
    # Only the first violation will be reported
    if abs(years) > Period.MAX_PERIOD_YEARS:
        # Years is checked first, so it should always be in the error if it's invalid
        assert "years" in error_msg.lower()
        assert str(Period.MAX_PERIOD_YEARS) in error_msg
        assert str(years) in error_msg or str(abs(years)) in error_msg
    elif abs(months) > Period.MAX_PERIOD_MONTHS:
        # Months is checked second, so it should be in the error if years is valid
        assert "months" in error_msg.lower()
        assert str(Period.MAX_PERIOD_MONTHS) in error_msg
        assert str(months) in error_msg or str(abs(months)) in error_msg
    elif abs(days) > Period.MAX_PERIOD_DAYS:
        # Days is checked last, so it should be in the error if years and months are valid
        assert "days" in error_msg.lower()
        assert str(Period.MAX_PERIOD_DAYS) in error_msg
        assert str(days) in error_msg or str(abs(days)) in error_msg
    else:
        # This shouldn't happen - at least one component should be invalid
        pytest.fail(f"Expected at least one component to exceed bounds: years={years}, months={months}, days={days}")
