"""
DATE-SMT: A framework for symbolic analysis of date-based computations.

This package provides implementations for expressing and solving date constraints using Z3.
"""

from .api import DateSMTBuilder
from .core import Date, Period

# Import bitvector implementations
from .symbolic_bitvector.naive_bv import NaiveSolver as BitVectorNaiveSolver
from .symbolic_bitvector.epoch_days_bv import EpochDaysSolver as BitVectorEpochDaysSolver
from .symbolic_bitvector.hybrid_bv import HybridSolver as BitVectorHybridSolver
from .symbolic_bitvector.alpha_beta_bv import AlphaBetaSolver as BitVectorAlphaBetaSolver
from .symbolic_bitvector.alpha_beta_table_bv import AlphaBetaTableSolver as BitVectorAlphaBetaTableSolver

# Import integer implementations
from .symbolic_int.naive_int import NaiveSolver as IntNaiveSolver
from .symbolic_int.epoch_days_int import EpochDaysSolver as IntEpochDaysSolver
from .symbolic_int.hybrid_int import HybridSolver as IntHybridSolver
from .symbolic_int.alpha_beta_int import AlphaBetaSolver as IntAlphaBetaSolver
from .symbolic_int.alpha_beta_table_int import AlphaBetaTableSolver as IntAlphaBetaTableSolver


__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "DateSMTBuilder",
    # Bitvector implementations
    "BitVectorNaiveSolver",
    "BitVectorEpochDaysSolver",
    "BitVectorHybridSolver",
    "BitVectorAlphaBetaSolver",
    "BitVectorAlphaBetaTableSolver",
    # Integer implementations
    "IntNaiveSolver",
    "IntEpochDaysSolver",
    "IntHybridSolver",
    "IntAlphaBetaSolver",
    "IntAlphaBetaTableSolver",
]
