"""
DateSAT: A framework for symbolic analysis of date-based computations.

This package provides implementations for expressing and solving date constraints using Z3.
"""

from .api import DateSATBuilder
from .core import Date, Period
from .solver import solve, solve_from_json

# Import bitvector implementations
from .symbolic_bitvector.simple_bv import SimpleSolver as BitVectorSimpleSolver
from .symbolic_bitvector.epoch_days_bv import EpochDaysSolver as BitVectorEpochDaysSolver
from .symbolic_bitvector.hybrid_bv import HybridSolver as BitVectorHybridSolver
from .symbolic_bitvector.alpha_beta_bv import AlphaBetaSolver as BitVectorAlphaBetaSolver
from .symbolic_bitvector.alpha_beta_table_bv import AlphaBetaTableSolver as BitVectorAlphaBetaTableSolver

# Import integer implementations
from .symbolic_int.simple_int import SimpleSolver as IntSimpleSolver
from .symbolic_int.epoch_days_int import EpochDaysSolver as IntEpochDaysSolver
from .symbolic_int.hybrid_epoch_int import HybridEpochSolver as IntHybridEpochSolver
from .symbolic_int.hybrid_ymd_int import HybridYmdSolver as IntHybridYmdSolver
from .symbolic_int.alpha_beta_int import AlphaBetaSolver as IntAlphaBetaSolver
from .symbolic_int.alpha_beta_table_int import AlphaBetaTableSolver as IntAlphaBetaTableSolver


__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "DateSATBuilder",
    # High-level API
    "solve",
    "solve_from_json",
    # Bitvector implementations
    "BitVectorSimpleSolver",
    "BitVectorEpochDaysSolver",
    "BitVectorHybridSolver",
    "BitVectorAlphaBetaSolver",
    "BitVectorAlphaBetaTableSolver",
    # Integer implementations
    "IntSimpleSolver",
    "IntEpochDaysSolver",
    "IntHybridEpochSolver",
    "IntHybridYmdSolver",
    "IntAlphaBetaSolver",
    "IntAlphaBetaTableSolver",
]
