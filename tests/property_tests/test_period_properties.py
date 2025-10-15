"""
Property-based tests for Period class using Hypothesis.

These tests verify mathematical properties and invariants of the Period class
using generated test data.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from datesmt_int.core import Period


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
    def test_equality_reflexive_and_hash_consistent(self, y, m, d):
        """Period equality should be reflexive and hash should be consistent."""
        p = Period(y, m, d)
        assert p == p
        assert hash(p) == hash(p)

    @given(
        st.integers(-1000, 1000),
        st.integers(-1000, 1000),
        st.integers(-1000, 1000),
        st.integers(-1000, 1000),
        st.integers(-1000, 1000),
        st.integers(-1000, 1000),
    )
    def test_equality_symmetric(self, y1, m1, d1, y2, m2, d2):
        """Period equality should be symmetric."""
        p1 = Period(y1, m1, d1)
        p2 = Period(y2, m2, d2)

        if p1 == p2:
            assert p2 == p1
        else:
            assert p2 != p1

    @given(st.integers(-1000, 1000), st.integers(-1000, 1000), st.integers(-1000, 1000))
    def test_hash_consistency(self, y, m, d):
        """Hash should be consistent across multiple calls."""
        p = Period(y, m, d)
        hash1 = hash(p)
        hash2 = hash(p)
        assert hash1 == hash2

    @given(
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
        st.integers(-100, 100),
    )
    def test_equality_transitive(self, y1, m1, d1, y2, m2, d2, y3, m3, d3):
        """Period equality should be transitive."""
        p1 = Period(y1, m1, d1)
        p2 = Period(y2, m2, d2)
        p3 = Period(y3, m3, d3)

        # If p1 == p2 and p2 == p3, then p1 == p3
        if p1 == p2 and p2 == p3:
            assert p1 == p3

    @given(st.integers(-1000, 1000), st.integers(-1000, 1000), st.integers(-1000, 1000))
    def test_string_representation_conversion(self, y, m, d):
        """String representation should be consistent."""
        p = Period(y, m, d)
        # The string representation should contain the values
        repr_str = repr(p)
        assert str(y) in repr_str
        assert str(m) in repr_str
        assert str(d) in repr_str
