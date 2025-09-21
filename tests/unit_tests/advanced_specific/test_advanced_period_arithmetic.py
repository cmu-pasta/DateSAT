"""
Unit tests for period arithmetic in the advanced approach.

Tests cover the to_days_approximate function and basic period arithmetic
using days-since-epoch conversion as implemented in the advanced approach.
"""

import pytest

from datesmt.core import Period
from datesmt.symbolic_advanced import to_days_approximate


class TestAdvancedPeriodArithmetic:
    """Test period arithmetic functions in advanced approach."""

    @pytest.mark.parametrize("period,expected_days", [
        # Basic cases
        (Period(0, 0, 0), 0),
        (Period(0, 0, 1), 1),
        (Period(0, 0, 30), 30),
        (Period(0, 1, 0), 30),  # 1 month = 30 days
        (Period(1, 0, 0), 365),  # 1 year = 365 days
        
        # Mixed components
        (Period(1, 2, 3), 1 * 365 + 2 * 30 + 3),  # 428
        (Period(2, 6, 10), 2 * 365 + 6 * 30 + 10),  # 800
        (Period(5, 3, 15), 5 * 365 + 3 * 30 + 15),  # 1900
        
        # Negative values
        (Period(-1, 0, 0), -365),
        (Period(0, -1, 0), -30),
        (Period(0, 0, -1), -1),
        (Period(-1, -2, -3), -1 * 365 + -2 * 30 + -3),  # -428
        
        # Large values
        (Period(10, 0, 0), 10 * 365),  # 3650
        (Period(0, 12, 0), 12 * 30),  # 360
        (Period(0, 0, 100), 100),
        (Period(10, 6, 15), 10 * 365 + 6 * 30 + 15),  # 3845
        
        # Edge cases
        (Period(100, 0, 0), 100 * 365),  # 36500
        (Period(0, 0, 365), 365),
        (Period(1, 12, 0), 1 * 365 + 12 * 30),  # 725
    ])
    def test_period_to_days_approximation(self, period, expected_days):
        """Test converting Period to approximate days."""
        days = to_days_approximate(period)
        assert days == expected_days, f"Period {period} should convert to {expected_days} days, got {days}"

    def test_period_to_days_approximation_properties(self):
        """Test mathematical properties of period to days conversion."""
        # Test commutativity of components
        p1 = Period(1, 2, 3)
        p2 = Period(2, 1, 3)
        p3 = Period(1, 3, 2)
        
        # All should have same total days
        days1 = to_days_approximate(p1)
        days2 = to_days_approximate(p2)
        days3 = to_days_approximate(p3)
        
        # Note: This is not true for period arithmetic, but is true for approximation
        # 1*365 + 2*30 + 3 = 365 + 60 + 3 = 428
        # 2*365 + 1*30 + 3 = 730 + 30 + 3 = 763
        # 1*365 + 3*30 + 2 = 365 + 90 + 2 = 457
        # So they're different, which is correct for approximation
        
        assert days1 == 428
        assert days2 == 763
        assert days3 == 457

    def test_period_to_days_zero_cases(self):
        """Test various zero period cases."""
        zero_cases = [
            Period(0, 0, 0),
            Period(0, 0, 0),
            Period(0, 0, 0),
        ]
        
        for period in zero_cases:
            days = to_days_approximate(period)
            assert days == 0, f"Zero period {period} should convert to 0 days"

    def test_period_to_days_negative_cases(self):
        """Test various negative period cases."""
        negative_cases = [
            (Period(-1, 0, 0), -365),
            (Period(0, -1, 0), -30),
            (Period(0, 0, -1), -1),
            (Period(-2, -3, -4), -2 * 365 + -3 * 30 + -4),
            (Period(-10, 0, 0), -10 * 365),
        ]
        
        for period, expected in negative_cases:
            days = to_days_approximate(period)
            assert days == expected, f"Negative period {period} should convert to {expected} days, got {days}"

    def test_period_to_days_large_values(self):
        """Test period conversion with large values."""
        large_cases = [
            (Period(100, 0, 0), 100 * 365),
            (Period(0, 24, 0), 24 * 30),  # 2 years in months
            (Period(0, 0, 1000), 1000),
            (Period(50, 12, 30), 50 * 365 + 12 * 30 + 30),
        ]
        
        for period, expected in large_cases:
            days = to_days_approximate(period)
            assert days == expected, f"Large period {period} should convert to {expected} days, got {days}"

    def test_period_to_days_approximation_consistency(self):
        """Test that approximation is consistent across multiple calls."""
        period = Period(5, 3, 15)
        
        # Multiple calls should return same result
        days1 = to_days_approximate(period)
        days2 = to_days_approximate(period)
        days3 = to_days_approximate(period)
        
        assert days1 == days2 == days3
        assert days1 == 5 * 365 + 3 * 30 + 15

    def test_period_to_days_approximation_monotonicity(self):
        """Test that approximation preserves ordering for simple cases."""
        # For same year/month, more days should give more total days
        p1 = Period(1, 1, 10)
        p2 = Period(1, 1, 20)
        p3 = Period(1, 1, 30)
        
        days1 = to_days_approximate(p1)
        days2 = to_days_approximate(p2)
        days3 = to_days_approximate(p3)
        
        assert days1 < days2 < days3
        
        # For same year/days, more months should give more total days
        p4 = Period(1, 1, 10)
        p5 = Period(1, 2, 10)
        p6 = Period(1, 3, 10)
        
        days4 = to_days_approximate(p4)
        days5 = to_days_approximate(p5)
        days6 = to_days_approximate(p6)
        
        assert days4 < days5 < days6

    def test_period_to_days_approximation_edge_cases(self):
        """Test edge cases for period approximation."""
        edge_cases = [
            # Maximum reasonable values
            (Period(999, 0, 0), 999 * 365),
            (Period(0, 999, 0), 999 * 30),
            (Period(0, 0, 9999), 9999),
            
            # Minimum reasonable values
            (Period(-999, 0, 0), -999 * 365),
            (Period(0, -999, 0), -999 * 30),
            (Period(0, 0, -9999), -9999),
            
            # Mixed extreme values
            (Period(100, 50, 200), 100 * 365 + 50 * 30 + 200),
            (Period(-100, -50, -200), -100 * 365 + -50 * 30 + -200),
        ]
        
        for period, expected in edge_cases:
            days = to_days_approximate(period)
            assert days == expected, f"Edge case period {period} should convert to {expected} days, got {days}"

    def test_period_to_days_approximation_roundtrip_properties(self):
        """Test properties that should hold for approximation."""
        # Test that approximation is linear in each component
        base_period = Period(1, 2, 3)
        base_days = to_days_approximate(base_period)
        
        # Adding 1 year should add 365 days
        year_plus = Period(base_period.years + 1, base_period.months, base_period.days)
        year_plus_days = to_days_approximate(year_plus)
        assert year_plus_days == base_days + 365
        
        # Adding 1 month should add 30 days
        month_plus = Period(base_period.years, base_period.months + 1, base_period.days)
        month_plus_days = to_days_approximate(month_plus)
        assert month_plus_days == base_days + 30
        
        # Adding 1 day should add 1 day
        day_plus = Period(base_period.years, base_period.months, base_period.days + 1)
        day_plus_days = to_days_approximate(day_plus)
        assert day_plus_days == base_days + 1

    def test_period_to_days_approximation_identity(self):
        """Test identity properties of period approximation."""
        # Zero period should be identity
        zero = Period(0, 0, 0)
        assert to_days_approximate(zero) == 0
        
        # Period with all zeros should be zero
        assert to_days_approximate(Period(0, 0, 0)) == 0
        
        # Period with negative zeros should still be zero
        assert to_days_approximate(Period(-0, -0, -0)) == 0

    def test_period_to_days_approximation_symmetry(self):
        """Test symmetry properties of period approximation."""
        # Positive and negative periods should be symmetric
        pos_period = Period(1, 2, 3)
        neg_period = Period(-1, -2, -3)
        
        pos_days = to_days_approximate(pos_period)
        neg_days = to_days_approximate(neg_period)
        
        assert pos_days == -neg_days, f"Positive {pos_period} -> {pos_days}, negative {neg_period} -> {neg_days}"

    def test_period_to_days_approximation_comprehensive(self):
        """Comprehensive test of period approximation with many cases."""
        test_cases = [
            # (years, months, days, expected_days)
            (0, 0, 0, 0),
            (0, 0, 1, 1),
            (0, 0, 30, 30),
            (0, 1, 0, 30),
            (1, 0, 0, 365),
            (1, 1, 1, 365 + 30 + 1),
            (2, 3, 4, 2 * 365 + 3 * 30 + 4),
            (10, 0, 0, 10 * 365),
            (0, 12, 0, 12 * 30),
            (0, 0, 365, 365),
            (-1, 0, 0, -365),
            (0, -1, 0, -30),
            (0, 0, -1, -1),
            (-1, -1, -1, -365 - 30 - 1),
        ]
        
        for years, months, days, expected in test_cases:
            period = Period(years, months, days)
            result = to_days_approximate(period)
            assert result == expected, f"Period({years}, {months}, {days}) -> {result}, expected {expected}"
