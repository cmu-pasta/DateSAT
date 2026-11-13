"""
DateSAT: A framework for symbolic analysis of date-based computations.

This package provides implementations for expressing and solving date constraints using Z3.
"""

from .api import DateSATBuilder
from .core import Date, Period
from .solver import solve, solve_from_json

# Import integer implementations
from .symbolic_int.simple_int import SimpleSolver as IntSimpleSolver
from .symbolic_int.epoch_days_int import EpochDaysSolver as IntEpochDaysSolver
from .symbolic_int.hybrid_init_epoch_int import HybridInitEpochSolver as IntHybridInitEpochSolver
from .symbolic_int.hybrid_init_ymd_int import HybridInitYmdSolver as IntHybridInitYmdSolver
from .symbolic_int.alpha_beta_int import AlphaBetaSolver as IntAlphaBetaSolver


__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "DateSATBuilder",
    # High-level API
    "solve",
    "solve_from_json",
    # Integer implementations
    "IntSimpleSolver",
    "IntEpochDaysSolver",
    "IntHybridInitEpochSolver",
    "IntHybridInitYmdSolver",
    "IntAlphaBetaSolver",
]
