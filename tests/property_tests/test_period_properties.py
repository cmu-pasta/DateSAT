"""
Property-based tests for Period class using Hypothesis.

These tests verify mathematical properties and invariants of the Period class
using generated test data.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from datesmt.core import Period


class TestPeriodProperties:
    """Property-based tests for Period class."""

    @given(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
    )
    def test_constructor_roundtrips_values(self, y, m, d):
        """Period constructor should preserve the input values."""
        p = Period(y, m, d)
        assert (p.years, p.months, p.days) == (y, m, d)

    @given(st.integers(-1000, 1000), st.integers(-1000, 1000), st.integers(-1000, 1000))
    def test_hash_consistency(self, y, m, d):
        """Hash should be consistent across multiple calls."""
        p = Period(y, m, d)
        hash1 = hash(p)
        hash2 = hash(p)
        assert hash1 == hash2

    @given(st.integers(-1000, 1000), st.integers(-1000, 1000), st.integers(-1000, 1000))
    def test_string_representation_conversion(self, y, m, d):
        """String representation should be consistent."""
        p = Period(y, m, d)
        # The string representation should contain the values
        repr_str = repr(p)
        assert str(y) in repr_str
        assert str(m) in repr_str
        assert str(d) in repr_str
