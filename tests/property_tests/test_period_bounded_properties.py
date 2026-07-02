"""
Property-based tests for the bounded Period class in future_work.datesat_bounded.core.

This is the bounded twin of test_period_properties.py. datesat.core.Period no
longer enforces the MAX_PERIOD_* range checks; future_work.datesat_bounded.core.Period
still does, and this file targets that bounded class specifically.
"""

import pytest
from hypothesis import given, assume
from hypothesis import strategies as st

from future_work.datesat_bounded.core import Period


class TestBoundedPeriodProperties:
    """Property-based tests for the bounded Period class."""

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_constructor_roundtrips_values(self, y, m, d):
        """Bounded Period constructor should preserve values within its range."""
        p = Period(y, m, d)
        assert (p.years, p.months, p.days) == (y, m, d)

    @given(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.integers(min_value=-(10**9), max_value=10**9),
    )
    def test_large_values_rejected(self, y, m, d):
        """Very large integer values must be rejected by the bounded Period."""
        assume(
            abs(y) > Period.MAX_PERIOD_YEARS
            or abs(m) > Period.MAX_PERIOD_MONTHS
            or abs(d) > Period.MAX_PERIOD_DAYS
        )

        with pytest.raises(ValueError) as exc_info:
            Period(y, m, d)

        error_msg = str(exc_info.value)
        assert "out of range" in error_msg.lower()

        # Period checks in order: years, months, days - only first violation is reported.
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
    def test_addition_within_bounds(self, y1, m1, d1, y2, m2, d2):
        """Period addition should succeed when the result stays within bounds."""
        assume(abs(y1 + y2) <= Period.MAX_PERIOD_YEARS)
        assume(abs(m1 + m2) <= Period.MAX_PERIOD_MONTHS)
        assume(abs(d1 + d2) <= Period.MAX_PERIOD_DAYS)

        p1 = Period(y1, m1, d1)
        p2 = Period(y2, m2, d2)
        result = p1 + p2
        assert (result.years, result.months, result.days) == (y1 + y2, m1 + m2, d1 + d2)

    @given(
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
        st.integers(min_value=-Period.MAX_PERIOD_YEARS, max_value=Period.MAX_PERIOD_YEARS),
        st.integers(min_value=-Period.MAX_PERIOD_MONTHS, max_value=Period.MAX_PERIOD_MONTHS),
        st.integers(min_value=-Period.MAX_PERIOD_DAYS, max_value=Period.MAX_PERIOD_DAYS),
    )
    def test_addition_out_of_bounds_raises(self, y1, m1, d1, y2, m2, d2):
        """Period addition whose result exits the bounds must raise ValueError."""
        assume(
            abs(y1 + y2) > Period.MAX_PERIOD_YEARS
            or abs(m1 + m2) > Period.MAX_PERIOD_MONTHS
            or abs(d1 + d2) > Period.MAX_PERIOD_DAYS
        )
        p1 = Period(y1, m1, d1)
        p2 = Period(y2, m2, d2)
        with pytest.raises(ValueError):
            p1 + p2
