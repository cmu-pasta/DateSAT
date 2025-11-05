"""
Property-based tests for Period class using Hypothesis.

These tests verify mathematical properties and invariants of the Period class
using generated test data.
"""

import pytest
from hypothesis import given, assume
from hypothesis import strategies as st

from datesmt.core import Period


class TestPeriodProperties:
    """Property-based tests for Period class."""

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_constructor_roundtrips_values(self, y, m, d):
        """Period constructor should preserve the input values within bounds."""
        p = Period(y, m, d)
        assert (p.years, p.months, p.days) == (y, m, d)

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_hash_consistency(self, y, m, d):
        """Hash should be consistent across multiple calls."""
        p = Period(y, m, d)
        hash1 = hash(p)
        hash2 = hash(p)
        assert hash1 == hash2

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_string_representation_conversion(self, y, m, d):
        """String representation should be consistent."""
        p = Period(y, m, d)
        # The string representation should contain the values
        str_repr = str(p)
        assert str(y) in str_repr
        assert str(m) in str_repr
        assert str(d) in str_repr

    @given(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
    )
    def test_large_values_rejected(self, y, m, d):
        """Very large Period values should be rejected with ValueError."""
        # Assume at least one component exceeds bounds
        assume(
            abs(y) > Period.MAX_PERIOD_YEARS
            or abs(m) > Period.MAX_PERIOD_MONTHS
            or abs(d) > Period.MAX_PERIOD_DAYS
        )
        
        with pytest.raises(ValueError) as exc_info:
            Period(y, m, d)
        
        error_msg = str(exc_info.value)
        assert "out of range" in error_msg.lower()
        
        # Verify the error mentions which component(s) are invalid
        # (Note: Period checks in order: years, months, days, so only first violation is reported)
        if abs(y) > Period.MAX_PERIOD_YEARS:
            assert "years" in error_msg.lower()
        elif abs(m) > Period.MAX_PERIOD_MONTHS:
            assert "months" in error_msg.lower()
        elif abs(d) > Period.MAX_PERIOD_DAYS:
            assert "days" in error_msg.lower()

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_period_addition_within_bounds(self, y1, m1, d1, y2, m2, d2):
        """Period addition should work when result stays within bounds."""
        # Only test when addition result stays within bounds
        assume(abs(y1 + y2) <= Period.MAX_PERIOD_YEARS)
        assume(abs(m1 + m2) <= Period.MAX_PERIOD_MONTHS)
        assume(abs(d1 + d2) <= Period.MAX_PERIOD_DAYS)
        
        p1 = Period(y1, m1, d1)
        p2 = Period(y2, m2, d2)
        result = p1 + p2
        
        assert result.years == y1 + y2
        assert result.months == m1 + m2
        assert result.days == d1 + d2

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
        st.integers(min_value=-10, max_value=10),
    )
    def test_period_multiplication_within_bounds(self, y, m, d, multiplier):
        """Period multiplication should work when result stays within bounds."""
        # Only test when multiplication result stays within bounds
        assume(abs(y * multiplier) <= Period.MAX_PERIOD_YEARS)
        assume(abs(m * multiplier) <= Period.MAX_PERIOD_MONTHS)
        assume(abs(d * multiplier) <= Period.MAX_PERIOD_DAYS)
        
        p = Period(y, m, d)
        result = p * multiplier
        
        assert result.years == y * multiplier
        assert result.months == m * multiplier
        assert result.days == d * multiplier
