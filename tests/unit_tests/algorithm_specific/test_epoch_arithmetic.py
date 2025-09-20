"""
Unit tests for epoch date arithmetic in datesmt.symbolic_advanced.

Tests cover the to_days_since_epoch and from_days_since_epoch functions
with March 1, 2000 as the epoch date.
"""

import pytest

from datesmt.core import Date
from datesmt.symbolic_advanced import from_days_since_epoch, to_days_since_epoch


class TestEpochDateArithmetic:
    """Test epoch date arithmetic functions."""

    def test_epoch_date_is_zero(self):
        """Test that March 1, 2000 is day 0 (the epoch)."""
        epoch_date = Date(2000, 3, 1)
        days = to_days_since_epoch(epoch_date)
        assert days == 0, f"March 1, 2000 should be day 0, got {days}"

    def test_epoch_date_roundtrip(self):
        """Test that epoch date converts back to itself."""
        epoch_date = Date(2000, 3, 1)
        days = to_days_since_epoch(epoch_date)
        converted_date = from_days_since_epoch(days)
        assert (
            converted_date == epoch_date
        ), f"Epoch date roundtrip failed: {epoch_date} -> {days} -> {converted_date}"

    def test_dates_before_epoch_negative_days(self):
        """Test that dates before March 1, 2000 return negative days."""
        test_cases = [
            (Date(2000, 1, 1), -60),  # Jan 1, 2000 (31+29=60 days before March 1)
            (Date(2000, 2, 29), -1),  # Feb 29, 2000 (1 day before March 1)
            (Date(2000, 2, 28), -2),  # Feb 28, 2000 (2 days before March 1)
            (Date(1999, 12, 31), -61),  # Dec 31, 1999
            (Date(1999, 3, 1), -366),  # March 1, 1999 (2000 is leap year)
        ]

        for date_obj, expected_days in test_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"{date_obj} should be {expected_days} days, got {days}"

    def test_dates_after_epoch_positive_days(self):
        """Test that dates after March 1, 2000 return positive days."""
        test_cases = [
            (Date(2000, 3, 2), 1),  # March 2, 2000
            (Date(2000, 4, 1), 31),  # April 1, 2000 (31 days in March)
            (Date(2000, 5, 1), 61),  # May 1, 2000 (31+30=61 days)
            (Date(2001, 3, 1), 365),  # March 1, 2001 (2000 is leap year)
            (Date(2001, 3, 2), 366),  # March 2, 2001
        ]

        for date_obj, expected_days in test_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"{date_obj} should be {expected_days} days, got {days}"

    def test_bidirectional_conversion_accuracy(self):
        """Test that date -> days -> date conversion is accurate."""
        test_dates = [
            Date(1999, 1, 1),
            Date(1999, 12, 31),
            Date(2000, 1, 1),
            Date(2000, 2, 29),  # Leap year
            Date(2000, 3, 1),  # Epoch
            Date(2000, 3, 2),
            Date(2000, 12, 31),
            Date(2001, 1, 1),
            Date(2001, 2, 28),  # Non-leap year
            Date(2001, 3, 1),
            Date(2020, 2, 29),  # Leap year
            Date(2023, 6, 15),
            Date(2024, 2, 29),  # Leap year
        ]

        for original_date in test_dates:
            days = to_days_since_epoch(original_date)
            converted_date = from_days_since_epoch(days)
            assert (
                converted_date == original_date
            ), f"Bidirectional conversion failed: {original_date} -> {days} -> {converted_date}"

    def test_leap_year_handling(self):
        """Test proper handling of leap years in epoch calculations."""
        # Test leap year 2000
        leap_2000_cases = [
            (Date(2000, 2, 28), -2),  # Feb 28, 2000
            (Date(2000, 2, 29), -1),  # Feb 29, 2000 (leap day)
            (Date(2000, 3, 1), 0),  # March 1, 2000 (epoch)
        ]

        for date_obj, expected_days in leap_2000_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"Leap year 2000: {date_obj} should be {expected_days} days, got {days}"

        # Test non-leap year 2001
        non_leap_2001_cases = [
            (Date(2001, 2, 28), 364),  # Feb 28, 2001 (365-1 days from March 1, 2000)
            (Date(2001, 3, 1), 365),  # March 1, 2001
        ]

        for date_obj, expected_days in non_leap_2001_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"Non-leap year 2001: {date_obj} should be {expected_days} days, got {days}"

    def test_month_boundaries(self):
        """Test dates at month boundaries."""
        boundary_cases = [
            # January boundaries
            (Date(2000, 1, 1), -60),
            (Date(2000, 1, 31), -30),
            # February boundaries (leap year 2000)
            (Date(2000, 2, 1), -29),
            (Date(2000, 2, 29), -1),
            # March boundaries (epoch month)
            (Date(2000, 3, 1), 0),
            (Date(2000, 3, 31), 30),
            # April boundaries
            (Date(2000, 4, 1), 31),
            (Date(2000, 4, 30), 60),
        ]

        for date_obj, expected_days in boundary_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"Month boundary: {date_obj} should be {expected_days} days, got {days}"

    def test_year_boundaries(self):
        """Test dates at year boundaries."""
        year_boundary_cases = [
            # Year 1999 to 2000
            (Date(1999, 12, 31), -61),
            (Date(2000, 1, 1), -60),
            # Year 2000 to 2001
            (Date(2000, 12, 31), 305),  # 31+29+31+30+31+30+31+31+30+31+30+31-1 = 305
            (Date(2001, 1, 1), 306),
        ]

        for date_obj, expected_days in year_boundary_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"Year boundary: {date_obj} should be {expected_days} days, got {days}"

    def test_negative_days_conversion(self):
        """Test conversion of negative days back to dates."""
        negative_day_cases = [
            (-1, Date(2000, 2, 29)),  # 1 day before epoch
            (-2, Date(2000, 2, 28)),  # 2 days before epoch
            (-30, Date(2000, 1, 31)),  # 30 days before epoch
            (-60, Date(2000, 1, 1)),  # 60 days before epoch
            (-61, Date(1999, 12, 31)),  # 61 days before epoch
        ]

        for days, expected_date in negative_day_cases:
            converted_date = from_days_since_epoch(days)
            assert (
                converted_date == expected_date
            ), f"Negative days {days} should convert to {expected_date}, got {converted_date}"

    def test_positive_days_conversion(self):
        """Test conversion of positive days back to dates."""
        positive_day_cases = [
            (0, Date(2000, 3, 1)),  # Epoch
            (1, Date(2000, 3, 2)),  # 1 day after epoch
            (30, Date(2000, 3, 31)),  # 30 days after epoch
            (31, Date(2000, 4, 1)),  # 31 days after epoch
            (365, Date(2001, 3, 1)),  # 1 year after epoch (2000 is leap year)
        ]

        for days, expected_date in positive_day_cases:
            converted_date = from_days_since_epoch(days)
            assert (
                converted_date == expected_date
            ), f"Positive days {days} should convert to {expected_date}, got {converted_date}"

    def test_edge_case_century_leap_year(self):
        """Test edge case of century leap year (2000)."""
        # 2000 is a century leap year (divisible by 400)
        century_leap_cases = [
            (Date(2000, 2, 29), -1),  # Feb 29, 2000 exists
            (Date(2001, 2, 28), 364),  # Feb 29, 2001 doesn't exist
        ]

        for date_obj, expected_days in century_leap_cases:
            days = to_days_since_epoch(date_obj)
            assert (
                days == expected_days
            ), f"Century leap year: {date_obj} should be {expected_days} days, got {days}"

    def test_large_year_differences(self):
        """Test epoch arithmetic with large year differences."""
        large_year_cases = [
            (Date(1900, 1, 1), -36525),  # ~100 years before epoch
            (Date(2100, 12, 31), 36890),  # ~100 years after epoch
        ]

        for date_obj, expected_days in large_year_cases:
            days = to_days_since_epoch(date_obj)
            # Allow some tolerance for approximation
            assert (
                abs(days - expected_days) <= 1
            ), f"Large year difference: {date_obj} should be ~{expected_days} days, got {days}"

    def test_epoch_consistency(self):
        """Test that epoch date is consistently handled across all operations."""
        epoch_date = Date(2000, 3, 1)

        # Test multiple conversions
        for _ in range(10):
            days = to_days_since_epoch(epoch_date)
            assert days == 0, f"Epoch date should always be 0 days, got {days}"

            converted = from_days_since_epoch(0)
            assert (
                converted == epoch_date
            ), f"Day 0 should always convert to epoch date, got {converted}"

    def test_zero_days_edge_case(self):
        """Test that zero days correctly maps to epoch date."""
        zero_days_date = from_days_since_epoch(0)
        expected_epoch = Date(2000, 3, 1)
        assert (
            zero_days_date == expected_epoch
        ), f"Zero days should map to epoch date {expected_epoch}, got {zero_days_date}"

    def test_roundtrip_preservation(self):
        """Test that roundtrip conversion preserves all date information."""
        test_dates = [
            Date(1999, 12, 31),
            Date(2000, 1, 1),
            Date(2000, 2, 29),  # Leap day
            Date(2000, 3, 1),  # Epoch
            Date(2000, 12, 31),
            Date(2001, 1, 1),
            Date(2001, 2, 28),  # Non-leap year
            Date(2020, 2, 29),  # Leap year
            Date(2023, 6, 15),
        ]

        for original_date in test_dates:
            # Convert to days and back
            days = to_days_since_epoch(original_date)
            converted_date = from_days_since_epoch(days)

            # Verify all components are preserved
            assert (
                converted_date.year == original_date.year
            ), f"Year not preserved: {original_date} -> {converted_date}"
            assert (
                converted_date.month == original_date.month
            ), f"Month not preserved: {original_date} -> {converted_date}"
            assert (
                converted_date.day == original_date.day
            ), f"Day not preserved: {original_date} -> {converted_date}"
            assert (
                converted_date == original_date
            ), f"Date not preserved: {original_date} -> {converted_date}"
