"""
Alpha-beta DATE-SMT implementation using epoch-based conversion.

This module implements the alpha-beta approach where dates are represented
as (months, days) since an epoch.
"""

from typing import List, Tuple, Union

from z3 import (
    And,
    ArithRef,
    BoolRef,
    CheckSatResult,
    If,
    Int,
    IntVal,
    ModelRef,
    Not,
    Optimize,
    Or,
    Solver,
    sat,
    unknown,
    unsat,
)
from ..core import Date, Period
from .naive_int import eom_clamp, days_in_month, to_ordinal, from_ordinal

# -------------------------------
# Alpha (months-since-epoch) helpers
# Epoch month: 2000-03 (alpha = 0)
# alpha = 12*y + m - (12*2000 + 3)
# Inverse: let k = alpha + (12*2000 + 3), then
#   y = (k - 1) / 12
#   m = k - 12*y
# -------------------------------
# Python int epoch constants (for arithmetic outside Z3)
_EPOCH_YEAR = 2000
_EPOCH_MONTH = 3
# Z3 epoch constants
_EPOCH_LINEAR = _EPOCH_YEAR * 12 + _EPOCH_MONTH  # 12*2000 + 3
# Alpha bounds constants (months since epoch)
_ALPHA_MIN = (1900 - _EPOCH_YEAR) * 12 + (3 - _EPOCH_MONTH)  # -1200
_ALPHA_MAX = (2100 - _EPOCH_YEAR) * 12 + (2 - _EPOCH_MONTH)  # 1199


def months_since_epoch_from_ym(y, m) -> ArithRef:
    """Z3-pure: compute months-since-epoch (alpha) from year/month."""
    return (y * 12 + m) - _EPOCH_LINEAR


def ym_from_months_since_epoch(alpha) -> Tuple[ArithRef, ArithRef]:
    """Z3-pure inverse: decode (year, month) from alpha months-since-epoch."""
    k = alpha + _EPOCH_LINEAR
    y = (k - IntVal(1)) / 12
    m = k - y * 12
    return y, m


class DateVar:
    """Symbolic date variable using alpha-beta representation.

    alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
    beta  (beta_var):   extra days within that month (0-based), so DOM = 1+beta
    """

    def __init__(self, name: str, bounded: bool = False, solver=None):
        """Create a symbolic date variable.
        
        Args:
            name: Name of the date variable
            bounded: If True, add date validation bounds (requires solver)
            solver: Solver instance for adding constraints (required if bounded=True)
        """
        self.name = name
        self._bounded = bounded
        # Only store solver if bounded (needed to add bounds and equality constraints)
        self._solver = solver if bounded else None
        # Alpha: Z3 integer variable for months since epoch-month
        self.months_var = Int(f"{name}_months")
        # Beta: Z3 integer variable for extra days (0-based) within month
        self.beta_var = Int(f"{name}_beta")

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    @property
    def year(self) -> ArithRef:
        """Get symbolic year component (decodes from months_var)."""
        y, _ = ym_from_months_since_epoch(self.months_var)
        return y

    @property
    def month(self) -> ArithRef:
        """Get symbolic month component (decodes from months_var)."""
        _, m = ym_from_months_since_epoch(self.months_var)
        return m

    @property
    def day(self) -> ArithRef:
        """Get symbolic day component (beta_var + 1, since beta is 0-based)."""
        return self.beta_var + IntVal(1)

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date using (alpha, beta)."""
        alpha_val = model.evaluate(self.months_var, model_completion=True).as_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_long()
        k = alpha_val + (_EPOCH_YEAR * 12 + _EPOCH_MONTH)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        try:
            return Date(year, month, day)
        except ValueError:
            # Intermediate result went out of bounds - use unbounded date
            return Date(year, month, day, bounded=False)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                IntVal(other.year), IntVal(other.month)
            )
            beta_o = IntVal(other.day - 1)

            return Or(
                self.months_var > alpha_o,
                And(self.months_var == alpha_o, self.beta_var >= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var > other.months_var,
                And(
                    self.months_var == other.months_var, self.beta_var >= other.beta_var
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                IntVal(other.year), IntVal(other.month)
            )
            beta_o = IntVal(other.day - 1)

            return Or(
                self.months_var < alpha_o,
                And(self.months_var == alpha_o, self.beta_var <= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var < other.months_var,
                And(
                    self.months_var == other.months_var, self.beta_var <= other.beta_var
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other) -> BoolRef:
        """Support x < date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other) -> BoolRef:
        """Support x > date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other) -> BoolRef:
        """Support x == date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                IntVal(other.year), IntVal(other.month)
            )
            beta_o = IntVal(other.day - 1)

            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        elif isinstance(other, DateVar):
            return And(
                self.months_var == other.months_var, self.beta_var == other.beta_var
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison using ordinal arithmetic."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def _add_bounds(self) -> None:
        """Add date validation bounds to this DateVar if bounded and solver is available."""
        if not self._bounded or self._solver is None:
            return
        
        # Alpha bounds: months since 2000-03
        # 1900-03 => -1200, 2100-02 => 1199
        self._solver.add(self.months_var >= IntVal(_ALPHA_MIN))
        self._solver.add(self.months_var <= IntVal(_ALPHA_MAX))

        # Beta bounds depend on month length: 0 <= beta < days_in_month(y,m)
        y, m = ym_from_months_since_epoch(self.months_var)
        self._solver.add(self.beta_var >= 0)
        self._solver.add(self.beta_var < days_in_month(y, m))

    def __add__(self, other) -> "DateVar":
        """DateVar + Period using alpha for Y/M and beta for D.
        Steps:
          - Fast path: If days-only period, add days directly to beta, then normalize.
          - Full path: Add months to alpha, EOM clamp beta, add days to beta, then normalize.
        """
        if isinstance(other, Period):
            # Create intermediate result with bounds (following naive/epoch_days pattern)
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d",
                bounded=self._bounded,  # Inherit boundedness from parent
                solver=self._solver
            )
            months_delta = IntVal(other.years * 12 + other.months)
            days_delta = IntVal(other.days)

            # Fast path: days-only period
            if other.years == 0 and other.months == 0:
                # Add days directly to beta
                new_beta = self.beta_var + days_delta
                
                # Normalize: convert (alpha, new_beta) to ordinal, then back to normalized (alpha, beta)
                # This handles arbitrary month overflows correctly
                y0, m0 = ym_from_months_since_epoch(self.months_var)
                d0 = new_beta + IntVal(1)  # Convert 0-based beta to 1-based day
                
                # Convert to ordinal (this represents the date with potential overflow)
                ordinal = to_ordinal(y0, m0, d0)
                
                # Convert back to normalized (alpha, beta) - this handles all overflow cases
                y2, m2, d2 = from_ordinal(ordinal)
                
                months_expr = months_since_epoch_from_ym(y2, m2)
                beta_expr = d2 - IntVal(1)
                
                # Link the computed expressions to the result's variables
                if result._solver is not None:
                    result._solver.add(result.months_var == months_expr)
                    result._solver.add(result.beta_var == beta_expr)
                
                # Add bounds to intermediate result
                result._add_bounds()
                return result

            # Full path: Add to alpha and beta directly, then normalize
            # Step 1: Add months to alpha directly
            alpha1 = self.months_var + months_delta
            y1, m1 = ym_from_months_since_epoch(alpha1)

            # Step 2: EOM clamp beta (needed when adding months - e.g., Jan 31 + 1 month = Feb 28/29)
            d1 = eom_clamp(y1, m1, self.beta_var + IntVal(1))
            beta1 = d1 - IntVal(1)  # Convert back to 0-based beta

            # Step 3: Add days to beta directly
            new_beta = beta1 + days_delta

            # Step 4: Normalize via ordinal conversion (handles all overflow cases)
            d_temp = new_beta + IntVal(1)  # Convert 0-based beta to 1-based day
            ordinal = to_ordinal(y1, m1, d_temp)
            y2, m2, d2 = from_ordinal(ordinal)

            months_expr = months_since_epoch_from_ym(y2, m2)
            beta_expr = d2 - IntVal(1)
            
            # Link the computed expressions to the result's variables
            if result._solver is not None:
                result._solver.add(result.months_var == months_expr)
                result._solver.add(result.beta_var == beta_expr)
            
            # Add bounds to intermediate result
            result._add_bounds()
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other) -> "DateVar":
        """DateVar - Period implemented as DateVar + (-Period)."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class AlphaBetaSolver:
    """Alpha-beta date constraint solver using epoch-based conversion."""

    def __init__(self, timeout_ms=600000, use_maxsat=False):
        """Initialize the solver with timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
            use_maxsat: If True, use MaxSAT optimization with soft constraints
        """
        self.use_maxsat = use_maxsat
        if use_maxsat:
            self.solver = Optimize()
        else:
            self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name, bounded=True, solver=self.solver)
        self.date_vars[name] = date_var

        # Add bounds for valid date ranges [1900-03-01 to 2100-02-28]
        date_var._add_bounds()

        return date_var

    def add_constraint(self, constraint: BoolRef) -> None:
        """Add a constraint to the solver."""
        self.constraints.append(constraint)
        self.solver.add(constraint)

    def check(self) -> CheckSatResult:
        """Check if constraints are satisfiable."""
        return self.solver.check()

    def model(self) -> ModelRef:
        """Get the model if satisfiable."""
        return self.solver.model()

    def get_concrete_dates(self, model: ModelRef) -> dict:
        """Get concrete dates from the model."""
        return {
            name: var.to_concrete_date(model) for name, var in self.date_vars.items()
        }

    def solve(self) -> Union[bool, dict]:
        """Solve the constraints."""
        # Add MaxSAT soft constraints if enabled
        if self.use_maxsat:
            from datetime import date

            today = date.today()
            # Calculate months since epoch for today
            today_months = (today.year - _EPOCH_YEAR) * 12 + (
                today.month - _EPOCH_MONTH
            )

            # Convert years to months
            months_50_years = 50 * 12  # 600 months
            months_10_years = 10 * 12  # 120 months

            # Add soft constraints for each date variable
            for name, date_var in self.date_vars.items():
                # High weight: today ± 50 years
                within_50_years = And(
                    date_var.months_var >= IntVal(today_months - months_50_years),
                    date_var.months_var <= IntVal(today_months + months_50_years),
                )
                self.solver.add_soft(within_50_years, weight=100)

                # Low weight: today ± 10 years
                within_10_years = And(
                    date_var.months_var >= IntVal(today_months - months_10_years),
                    date_var.months_var <= IntVal(today_months + months_10_years),
                )
                self.solver.add_soft(within_10_years, weight=10)

        result = self.check()
        if result == sat:
            model = self.model()
            return {
                "status": "sat",
                "dates": self.get_concrete_dates(model),
            }
        elif result == unsat:
            return {"status": "unsat", "dates": {}}
        else:
            # result == unknown (timeout or resource limit)
            return {"status": "timeout", "dates": {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self) -> List[BoolRef]:
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())
