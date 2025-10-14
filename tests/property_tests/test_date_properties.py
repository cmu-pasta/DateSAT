"""
Property-based tests for Date class using Hypothesis.

These tests verify mathematical properties and invariants of the Date class
using generated test data.
"""

from datetime import date as pydate

import pytest
from hypothesis import given
from hypothesis import strategies as st

from datesmt.core import Date


class TestDateProperties:
    """Property-based tests for Date class."""

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_round_conversion_property(self, d):
        """Converting Date to Python date and back should preserve the date."""
        custom = Date.from_python_date(d)
        back = custom.to_python_date()
        assert back == d

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_constructor_properties(self, d):
        """Date constructor should preserve values for valid inputs."""
        obj = Date(d.year, d.month, d.day)
        assert obj.year == d.year
        assert obj.month == d.month
        assert obj.day == d.day

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_equality_reflexive(self, d):
        """Date equality should be reflexive."""
        custom = Date.from_python_date(d)
        assert custom == custom
        assert hash(custom) == hash(custom)

    @given(
        st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)),
        st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)),
    )
    def test_equality_symmetric(self, d1, d2):
        """Date equality should be symmetric."""
        custom1 = Date.from_python_date(d1)
        custom2 = Date.from_python_date(d2)

        if custom1 == custom2:
            assert custom2 == custom1
        else:
            assert custom2 != custom1

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_hash_consistency(self, d):
        """Hash should be consistent across multiple calls."""
        custom = Date.from_python_date(d)
        hash1 = hash(custom)
        hash2 = hash(custom)
        assert hash1 == hash2

    @given(
        st.integers(min_value=1900, max_value=2100),
        st.integers(min_value=1, max_value=12),
        st.integers(min_value=1, max_value=29),
    )
    def test_leap_year_property(self, year, month, day):
        """Feb 29 should only be valid in leap years."""
        if month == 2 and day == 29:
            is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            if is_leap:
                Date(year, month, day)  # Should not raise
            else:
                with pytest.raises(ValueError):
                    Date(year, month, day)
