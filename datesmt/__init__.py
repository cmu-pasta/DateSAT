"""
DATE-SMT: A framework for symbolic analysis of date-based computations.

This package provides both baseline and advanced implementations for
expressing and solving date/time constraints using Z3.
"""

from .core import Date, Period
from .symbolic_advanced import DateVar as AdvancedDateVar
from .symbolic_advanced import PeriodVar as AdvancedPeriodVar
from .symbolic_api import DateSMTBuilder
from .symbolic_baseline import DateVar as BaselineDateVar
from .symbolic_baseline import PeriodVar as BaselinePeriodVar

__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "BaselineDateVar",
    "BaselinePeriodVar",
    "AdvancedDateVar",
    "AdvancedPeriodVar",
    "DateSMTBuilder",
]
