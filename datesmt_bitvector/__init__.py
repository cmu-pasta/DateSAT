"""
DATE-SMT: A framework for symbolic analysis of date-based computations.

This package provides both baseline and epoch_days implementations for
expressing and solving date/time constraints using Z3.
"""

from .core import Date, Period
from .symbolic_alpha_beta import AlphaBetaSolver
from .symbolic_alpha_beta_table import AlphaBetaTableSolver
from .symbolic_api import DateSMTBuilder
from .symbolic_baseline import BaselineSolver
from .symbolic_baseline import DateVar as BaselineDateVar
from .symbolic_baseline import PeriodVar as BaselinePeriodVar
from .symbolic_epoch_days import DateVar as EpochDaysDateVar
from .symbolic_epoch_days import EpochDaysSolver
from .symbolic_epoch_days import PeriodVar as EpochDaysPeriodVar
from .symbolic_hybrid import HybridSolver

__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "BaselineDateVar",
    "BaselinePeriodVar",
    "BaselineSolver",
    "EpochDaysDateVar",
    "EpochDaysPeriodVar",
    "EpochDaysSolver",
    "AlphaBetaSolver",
    "AlphaBetaTableSolver",
    "HybridSolver",
    "DateSMTBuilder",
]
