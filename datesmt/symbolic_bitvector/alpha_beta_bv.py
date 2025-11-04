"""
Alpha-beta DATE-SMT implementation using epoch-based conversion.

This module implements the alpha-beta approach where dates are represented
as (months, days) since an epoch.
"""

from typing import Union, Tuple, List
from z3 import (
    And,
    ArithRef,
    BitVec,
    BitVecVal,
    BoolRef,
    CheckSatResult,
    If,
    ModelRef,
    Not,
    Or,
    Solver,
    sat
)

from ..core import Date, Period
from .baseline_bv import eom_clamp, days_in_month, add_days_ordinal
from .bitwidths import LEGACY_BITS
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


def months_since_epoch_from_ym(y, m) -> ArithRef:
    """Z3-pure: compute months-since-epoch (alpha) from year/month."""
    return (y * BitVecVal(12, LEGACY_BITS) + m) - _EPOCH_LINEAR

def ym_from_months_since_epoch(alpha) -> Tuple[ArithRef, ArithRef]:
    """Z3-pure inverse: decode (year, month) from alpha months-since-epoch."""
    k = alpha + _EPOCH_LINEAR
    y = (k - BitVecVal(1, LEGACY_BITS)) / BitVecVal(12, LEGACY_BITS)
    m = k - y * BitVecVal(12, LEGACY_BITS)
    return y, m


class DateVar:
    """Symbolic date variable using alpha-beta representation.

    alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
    beta  (beta_var):   extra days within that month (0-based), so DOM = 1+beta
    """

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Alpha: Z3 bitvector variable for months since epoch-month
        self.months_var = BitVec(f"{name}_months", LEGACY_BITS)
        # Beta: Z3 bitvector variable for extra days (0-based) within month
        self.beta_var = BitVec(f"{name}_beta", LEGACY_BITS)

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date using (alpha, beta)."""
        alpha_val = model.evaluate(
            self.months_var, model_completion=True
        ).as_signed_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_signed_long()
        k = alpha_val + (_EPOCH_YEAR * 12 + _EPOCH_MONTH)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        return Date(year, month, day)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            # Convert Date to bitvector values if needed
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)

            return Or(
                self.months_var > alpha_o,
                And(self.months_var == alpha_o, self.beta_var >= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var > other.months_var,
                And(self.months_var == other.months_var, self.beta_var >= other.beta_var),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)

            return Or(
                self.months_var < alpha_o,
                And(self.months_var == alpha_o, self.beta_var <= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var < other.months_var,
                And(self.months_var == other.months_var, self.beta_var <= other.beta_var),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other) -> BoolRef:
        """Support x < date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other) -> BoolRef:
        """Support x > date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other) -> BoolRef:
        """Support x == date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)

            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        elif isinstance(other, DateVar):
            return And(self.months_var == other.months_var, self.beta_var == other.beta_var)
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison using ordinal arithmetic."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __add__(self, other) -> 'DateVar':
        """DateVar + Period using alpha for Y/M and beta for D.
        Steps:
          - Fast path: If days-only period, directly add to beta (within-month check handled by add_days_ordinal).
          - Otherwise add months to alpha, clamp EOM using current day,
            then add days in ordinal space and re-sync alpha/beta.
        """
        if isinstance(other, Period):
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
            )
            months_delta = BitVecVal(other.years * 12 + other.months, LEGACY_BITS)
            days_delta = BitVecVal(other.days, LEGACY_BITS)

            # Fast path: days-only period (skip month shift and EOM clamp)
            if other.years == 0 and other.months == 0:
                # Decode current (y,m,d) from (alpha,beta)
                y0, m0 = ym_from_months_since_epoch(self.months_var)
                d0 = self.beta_var + BitVecVal(1, LEGACY_BITS)
                
                # Add days (add_days_ordinal handles within-month fast path)
                y2, m2, d2 = add_days_ordinal(y0, m0, d0, days_delta)
                
                result.months_var = months_since_epoch_from_ym(y2, m2)
                result.beta_var = d2 - BitVecVal(1, LEGACY_BITS)
                return result

            # Full path: Decode current (y,m,d) from (alpha,beta)
            y0, m0 = ym_from_months_since_epoch(self.months_var)
            d0 = self.beta_var + BitVecVal(1, LEGACY_BITS)

            # Step 1: shift alpha by months
            alpha1 = self.months_var + months_delta
            y1, m1 = ym_from_months_since_epoch(alpha1)

            # Step 2: EOM clamp with current DOM
            d1 = eom_clamp(y1, m1, d0)

            # Step 3: add D days in ordinal space and resync alpha/beta
            y2, m2, d2 = add_days_ordinal(y1, m1, d1, days_delta)

            result.months_var = months_since_epoch_from_ym(y2, m2)
            result.beta_var = d2 - BitVecVal(1, LEGACY_BITS)
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other) -> 'DateVar':
        """DateVar - Period implemented as DateVar + (-Period)."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class AlphaBetaSolver:
    """Alpha-beta date constraint solver using epoch-based conversion."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Alpha bounds: months since 2000-03
        # 1900-03 => (1900-2000)*12 + (3-3)
        # 2100-02 => (2100-2000)*12 + (2-3)
        self.solver.add(
            date_var.months_var
            >= BitVecVal((1900 - _EPOCH_YEAR) * 12 + (3 - _EPOCH_MONTH), LEGACY_BITS)
        )
        self.solver.add(
            date_var.months_var
            <= BitVecVal((2100 - _EPOCH_YEAR) * 12 + (2 - _EPOCH_MONTH), LEGACY_BITS)
        )

        # Beta bounds depend on month length: 0 <= beta < days_in_month(y,m)
        y, m = ym_from_months_since_epoch(date_var.months_var)
        self.solver.add(date_var.beta_var >= BitVecVal(0, LEGACY_BITS))
        self.solver.add(date_var.beta_var < days_in_month(y, m))

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
        result = self.check()
        if result == sat:
            model = self.model()
            return {
                'status': 'sat',
                'dates': self.get_concrete_dates(model),
            }
        else:
            return {'status': 'unsat', 'dates': {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self) -> List[BoolRef]:
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())
