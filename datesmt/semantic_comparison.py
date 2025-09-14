"""
Semantic comparison utilities for DATE-SMT implementations.

This module provides functions to compare results from different
implementations based on their semantic meaning rather than object types.
"""

from typing import Any, Union

from .core import Date, Period


def compare_dates(date1: Any, date2: Any) -> bool:
    """Compare two Date objects semantically (by year, month, day)."""
    if not (
        hasattr(date1, 'year') and hasattr(date1, 'month') and hasattr(date1, 'day')
    ):
        return False
    if not (
        hasattr(date2, 'year') and hasattr(date2, 'month') and hasattr(date2, 'day')
    ):
        return False

    return (
        date1.year == date2.year
        and date1.month == date2.month
        and date1.day == date2.day
    )


def compare_periods(period1: Any, period2: Any) -> bool:
    """Compare two Period objects semantically (by years, months, days)."""
    if not (
        hasattr(period1, 'years')
        and hasattr(period1, 'months')
        and hasattr(period1, 'days')
    ):
        return False
    if not (
        hasattr(period2, 'years')
        and hasattr(period2, 'months')
        and hasattr(period2, 'days')
    ):
        return False

    return (
        period1.years == period2.years
        and period1.months == period2.months
        and period1.days == period2.days
    )


def semantic_equals(obj1: Any, obj2: Any) -> bool:
    """Compare two objects semantically based on their type and content."""
    # Handle None values
    if obj1 is None and obj2 is None:
        return True
    if obj1 is None or obj2 is None:
        return False

    # Handle tuples (for multiple return values)
    if isinstance(obj1, tuple) and isinstance(obj2, tuple):
        if len(obj1) != len(obj2):
            return False
        return all(semantic_equals(a, b) for a, b in zip(obj1, obj2))

    # Handle Date objects
    if (
        hasattr(obj1, 'year')
        and hasattr(obj1, 'month')
        and hasattr(obj1, 'day')
        and hasattr(obj2, 'year')
        and hasattr(obj2, 'month')
        and hasattr(obj2, 'day')
    ):
        return compare_dates(obj1, obj2)

    # Handle Period objects
    if (
        hasattr(obj1, 'years')
        and hasattr(obj1, 'months')
        and hasattr(obj1, 'days')
        and hasattr(obj2, 'years')
        and hasattr(obj2, 'months')
        and hasattr(obj2, 'days')
    ):
        return compare_periods(obj1, obj2)

    # Handle basic types
    return obj1 == obj2


def format_result(obj: Any) -> str:
    """Format an object for display in comparison results."""
    if obj is None:
        return "None"

    # Handle tuples
    if isinstance(obj, tuple):
        return f"({', '.join(format_result(item) for item in obj)})"

    # Handle Date objects
    if hasattr(obj, 'year') and hasattr(obj, 'month') and hasattr(obj, 'day'):
        return f"Date({obj.year}, {obj.month}, {obj.day})"

    # Handle Period objects
    if hasattr(obj, 'years') and hasattr(obj, 'months') and hasattr(obj, 'days'):
        return f"Period({obj.years}, {obj.months}, {obj.days})"

    # Handle other objects
    return str(obj)
