"""
Property-based tests for epoch conversion functions using Hypothesis.

These tests verify mathematical properties and invariants of the epoch conversion
functions using generated test data.
"""

from datetime import date as pydate

import pytest
from hypothesis import given
from hypothesis import strategies as st

from datesmt.core import Date
from datesmt.symbolic_epoch_days import from_days_since_epoch, to_days_since_epoch


class TestEpochConversionProperties:
    """Property-based tests for epoch conversion functions."""

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_epoch_conversion(self, d):
        """Converting to epoch and back should preserve the date."""
        custom_date = Date.from_python_date(d)
        epoch_days = to_days_since_epoch(custom_date)
        reconstructed = from_days_since_epoch(epoch_days)
        assert reconstructed == custom_date

    @given(
        st.integers(min_value=-36525, max_value=36523)
    )  # Allowed range from 1900-03-01 to 2100-02-28
    def test_epoch_conversion_inverse(self, days):
        """Converting from epoch and back should preserve the day count."""
        date_obj = from_days_since_epoch(days)
        reconstructed_days = to_days_since_epoch(date_obj)
        assert reconstructed_days == days

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_epoch_conversion_monotonic(self, d):
        """Epoch conversion should be monotonic (later dates have higher epoch values)."""
        custom_date = Date.from_python_date(d)
        epoch_days = to_days_since_epoch(custom_date)

        # Add one day and check it has higher epoch value
        next_day = custom_date.to_python_date() + pydate.resolution
        next_custom = Date.from_python_date(next_day)
        next_epoch = to_days_since_epoch(next_custom)
        assert next_epoch > epoch_days

    @given(st.dates(min_value=pydate(2000, 1, 1), max_value=pydate(2000, 12, 31)))
    def test_epoch_year_2000_properties(self, d):
        """Test specific properties around the epoch year 2000."""
        custom_date = Date.from_python_date(d)
        epoch_days = to_days_since_epoch(custom_date)

        # March 1, 2000 should be day 0
        if custom_date.year == 2000 and custom_date.month == 3 and custom_date.day == 1:
            assert epoch_days == 0

    @given(st.dates(min_value=pydate(1900, 3, 1), max_value=pydate(2100, 2, 28)))
    def test_epoch_conversion_consistency(self, d):
        """Multiple calls to epoch conversion should be consistent."""
        custom_date = Date.from_python_date(d)
        epoch1 = to_days_since_epoch(custom_date)
        epoch2 = to_days_since_epoch(custom_date)
        assert epoch1 == epoch2

    @given(st.integers(min_value=1, max_value=100))
    def test_epoch_arithmetic_properties(self, days_offset):
        """Test that epoch arithmetic works correctly."""
        # Start with a known date
        base_date = Date(2000, 3, 1)  # Epoch date
        base_epoch = to_days_since_epoch(base_date)

        # Add days and verify
        target_date = from_days_since_epoch(base_epoch + days_offset)
        target_epoch = to_days_since_epoch(target_date)

        assert target_epoch == base_epoch + days_offset
