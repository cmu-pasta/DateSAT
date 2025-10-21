"""
DATE-SMT: A framework for symbolic analysis of date-based computations.

This package provides both baseline and epoch_days implementations for
expressing and solving date/time constraints using Z3.
"""

from .api import DateSMTBuilder, create_bitvector_solver, create_int_solver
from .concrete import BaselineConcreteSolver, ConcreteDateVar
from .core import Date, Period
from .symbolic_bitvector.alpha_beta_bv import (
    AlphaBetaSolver as BitVectorAlphaBetaSolver,
)
from .symbolic_bitvector.alpha_beta_table_bv import (
    AlphaBetaTableSolver as BitVectorAlphaBetaTableSolver,
)

# Import bitvector implementations
from .symbolic_bitvector.baseline_bv import BaselineSolver as BitVectorBaselineSolver
from .symbolic_bitvector.epoch_days_bv import (
    EpochDaysSolver as BitVectorEpochDaysSolver,
)
from .symbolic_bitvector.hybrid_bv import HybridSolver as BitVectorHybridSolver
from .symbolic_int.alpha_beta_int import AlphaBetaSolver as IntAlphaBetaSolver
from .symbolic_int.alpha_beta_table_int import (
    AlphaBetaTableSolver as IntAlphaBetaTableSolver,
)

# Import integer implementations
from .symbolic_int.baseline_int import BaselineSolver as IntBaselineSolver
from .symbolic_int.epoch_days_int import EpochDaysSolver as IntEpochDaysSolver
from .symbolic_int.hybrid_int import HybridSolver as IntHybridSolver

__version__ = "0.1.0"
__all__ = [
    "Date",
    "Period",
    "DateSMTBuilder",
    "create_int_solver",
    "create_bitvector_solver",
    # Concrete implementation
    "BaselineConcreteSolver",
    "ConcreteDateVar",
    # Bitvector implementations
    "BitVectorBaselineSolver",
    "BitVectorEpochDaysSolver",
    "BitVectorHybridSolver",
    "BitVectorAlphaBetaSolver",
    "BitVectorAlphaBetaTableSolver",
    # Integer implementations
    "IntBaselineSolver",
    "IntEpochDaysSolver",
    "IntHybridSolver",
    "IntAlphaBetaSolver",
    "IntAlphaBetaTableSolver",
]
