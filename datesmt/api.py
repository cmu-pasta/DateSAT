"""
Unified API for DATE-SMT.

This module provides a unified interface for both bitvector and integer
approaches to DATE-SMT constraint solving.
"""

from typing import Any, Dict, List, Union

from z3 import BoolRef

from .core import Date, Period, _UnboundedDate


class DateSMTBuilder:
    """Unified API for DATE-SMT constraint solving."""

    def __init__(
        self,
        approach: str = "epoch_days",
        implementation: str = "int",
        timeout_ms: int = 600000,
    ):
        """Initialize the builder with the specified approach, implementation, and timeout.

        Args:
            approach: Either "naive", "epoch_days", "hybrid", "alpha_beta", or "alpha_beta_table"
            implementation: Either "int" or "bitvector" (default: "int")
            timeout_ms: Timeout in milliseconds (default: 600000 = 10 minutes)
        """
        self.approach = approach
        self.implementation = implementation
        self.timeout_ms = timeout_ms

        # Import the appropriate solver based on implementation
        if implementation == "bitvector":
            from .symbolic_bitvector.alpha_beta_bv import AlphaBetaSolver
            from .symbolic_bitvector.alpha_beta_table_bv import AlphaBetaTableSolver
            from .symbolic_bitvector.naive_bv import NaiveSolver
            from .symbolic_bitvector.epoch_days_bv import EpochDaysSolver
            from .symbolic_bitvector.hybrid_bv import HybridSolver
        elif implementation == "int":
            from .symbolic_int.alpha_beta_int import AlphaBetaSolver
            from .symbolic_int.alpha_beta_table_int import AlphaBetaTableSolver
            from .symbolic_int.naive_int import NaiveSolver
            from .symbolic_int.epoch_days_int import EpochDaysSolver
            from .symbolic_int.hybrid_int import HybridSolver
        else:
            raise ValueError(
                f"Unknown implementation: {implementation}. Must be 'int' or 'bitvector'"
            )

        # Initialize the appropriate solver
        if approach == "naive":
            self.solver = NaiveSolver(timeout_ms=timeout_ms)
        elif approach == "epoch_days":
            self.solver = EpochDaysSolver(timeout_ms=timeout_ms)
        elif approach == "hybrid":
            self.solver = HybridSolver(timeout_ms=timeout_ms)
        elif approach == "alpha_beta":
            self.solver = AlphaBetaSolver(timeout_ms=timeout_ms)
        elif approach == "alpha_beta_table":
            self.solver = AlphaBetaTableSolver(timeout_ms=timeout_ms)
        else:
            raise ValueError(
                f"Unknown approach: {approach}. Must be 'naive', 'epoch_days', 'hybrid', 'alpha_beta', or 'alpha_beta_table'"
            )

        self.constraints = []
        self._print_smt_on_solve = False
        
        # Track Int and Bool variables for complete solution extraction
        self.int_vars = {}  # name -> z3 var
        self.bool_vars = {}  # name -> z3 var

    def add_date_var(self, name: str) -> "DateVar":
        """Add a symbolic date variable."""
        return self.solver.add_date_var(name)

    def add_int_var(self, name: str, min_value: int = None, max_value: int = None) -> Any:
        """Add a symbolic int variable compatible with the current implementation.
        
        In bitvector mode, creates a BitVec with automatic bounds to prevent overflow.
        In int mode, creates an Int (unbounded by default).
        
        Args:
            name: Variable name
            min_value: Optional minimum value (default: 0 in bitvector mode, unbounded in int mode)
            max_value: Optional maximum value (default: 8000 in bitvector mode, unbounded in int mode)
        """
        if self.implementation == "bitvector":
            from z3 import BitVec, BitVecVal
            from .symbolic_bitvector.bitwidths import INT_VAR_BITS
            var = BitVec(name, INT_VAR_BITS)
            
            # Add automatic bounds to prevent bitvector overflow artifacts
            # These bounds prevent Z3 from finding spurious solutions due to modular wraparound
            # Keep values within 21-bit signed range (±1,048,575) to avoid overflow in arithmetic
            if min_value is None:
                min_value = 0  # Most integer variables represent non-negative quantities (counts, periods, etc.)
            if max_value is None:
                max_value = 8000   # Conservative bound to prevent arithmetic overflow in expressions like x*125
            
            # Add bound constraints
            self.solver.add_constraint(var >= BitVecVal(min_value, INT_VAR_BITS))
            self.solver.add_constraint(var <= BitVecVal(max_value, INT_VAR_BITS))
        else:
            from z3 import Int
            var = Int(name)
            
            # Add optional bounds in int mode if specified
            if min_value is not None:
                self.solver.add_constraint(var >= min_value)
            if max_value is not None:
                self.solver.add_constraint(var <= max_value)
        
        # Track this variable for solution extraction
        self.int_vars[name] = var
        return var

    def add_bool_var(self, name: str) -> Any:
        """Add a symbolic bool variable."""
        from z3 import Bool
        var = Bool(name)
        
        # Track this variable for solution extraction
        self.bool_vars[name] = var
        return var

    def add_constraint(self, constraint: Any) -> None:
        """Add a constraint to the solver.

        Accepts both Z3 BoolRef (for symbolic solvers) and ConstraintWrapper
        (for enumeration baseline).
        """
        # Guard against None constraints
        if constraint is None:
            raise TypeError(
                "Constraint is None. Ensure expressions return a valid constraint."
            )
        self.constraints.append(constraint)
        self.solver.add_constraint(constraint)

    def solve(self) -> Dict[str, Any]:
        """Solve the constraints and return results."""
        if self._print_smt_on_solve:
            print("\n; SMT-LIB dump (generated by DATE-SMT)")
            print(self.to_smt2())
        result = self.solver.solve()
        if result["status"] == "sat":
            # Extract Int and Bool variables from the Z3 model
            model = self.solver.model()
            int_values = {}
            bool_values = {}
            
            # Explicitly evaluate all tracked Int variables with model_completion=True
            # to ensure we get values for unconstrained variables
            for name, var in self.int_vars.items():
                try:
                    value = model.evaluate(var, model_completion=True)
                    if value is not None:
                        # Check if it's a BitVec or Int
                        from z3 import is_bv
                        if is_bv(value):
                            int_values[name] = value.as_signed_long()
                        else:
                            int_values[name] = value.as_long()
                except Exception:
                    # Skip if we can't extract the value
                    pass
            
            # Explicitly evaluate all tracked Bool variables with model_completion=True
            for name, var in self.bool_vars.items():
                try:
                    value = model.evaluate(var, model_completion=True)
                    if value is not None:
                        bool_values[name] = bool(value)
                except Exception:
                    # Skip if we can't extract the value
                    pass
            
            # Add Int and Bool values to result
            if int_values:
                result["ints"] = int_values
            if bool_values:
                result["bools"] = bool_values
            
            print(f"✅ SATISFIABLE:")
            for name, date in result["dates"].items():
                print(f"  {name} = {date}")
            for name, value in result.get("ints", {}).items():
                print(f"  {name} = {value}")
            for name, value in result.get("bools", {}).items():
                print(f"  {name} = {value}")
        else:
            print("❌ UNSATISFIABLE")
        return result

    def get_constraints(self) -> List[BoolRef]:
        """Get all constraints."""
        return self.constraints

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def enable_smtlib_print(self, enabled: bool = True) -> None:
        """Enable or disable printing SMT-LIB when solving."""
        self._print_smt_on_solve = enabled
