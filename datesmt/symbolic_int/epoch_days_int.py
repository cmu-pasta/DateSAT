"""
Epoch_days DATE-SMT implementation using epoch-based conversion.

This module implements the epoch_days approach where dates are represented
as days since an epoch, and period arithmetic is done using approximate
day conversions.
"""

from datetime import date, timedelta
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
from .naive_int import (
    _dbm_index,
    days_before_month,
    days_before_year,
    days_in_month,
    days_since_epoch_from_ymd,
    eom_clamp,
    normalize_month,
    ymd_from_days_since_epoch,
    _dbm_index,
)

_EPOCH = date(2000, 3, 1)


def from_days_since_epoch(days: int) -> Date:
    """Convert days since epoch to a Date."""
    result_date = _EPOCH + timedelta(days=days)
    return Date(result_date.year, result_date.month, result_date.day)


def to_days_since_epoch(date_obj: Date) -> int:
    """Convert a Date to days since epoch (March 1, 2000)."""
    target_python = date(date_obj.year, date_obj.month, date_obj.day)
    return (target_python - _EPOCH).days

def add_days_ordinal(y, m, d, delta_days) -> ArithRef:
    """
    Exact ordinal-based addition via a single ordinal add.
    """
    z = days_since_epoch_from_ymd(y, m, d)
    return z + delta_days

class DateVar:
    """Symbolic date variable for epoch_days implementation."""

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
        # Use a single Z3 integer variable for days since epoch
        self.days_var = Int(f"{name}_days")

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    @property
    def year(self) -> ArithRef:
        """Get symbolic year component (decodes from days_var)."""
        y, _, _ = ymd_from_days_since_epoch(self.days_var)
        return y

    @property
    def month(self) -> ArithRef:
        """Get symbolic month component (decodes from days_var)."""
        _, m, _ = ymd_from_days_since_epoch(self.days_var)
        return m

    @property
    def day(self) -> ArithRef:
        """Get symbolic day component (decodes from days_var)."""
        _, _, d = ymd_from_days_since_epoch(self.days_var)
        return d

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        days = model.evaluate(self.days_var, model_completion=True).as_long()
        return from_days_since_epoch(days)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            return self.days_var >= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var >= other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            return self.days_var <= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var <= other.days_var
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
            return self.days_var == to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var == other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def _add_bounds(self) -> None:
        """Add date validation bounds to this DateVar if bounded and solver is available."""
        if not self._bounded or self._solver is None:
            return
        
        # Add constraints for valid date ranges [1900-03-01 to 2100-02-28]
        # Epoch is March 1, 2000
        # 1900-03-01 = -36525 days from epoch
        # 2100-02-28 = 36523 days from epoch
        self._solver.add(self.days_var >= IntVal(-36525))
        self._solver.add(self.days_var <= IntVal(36523))

    def __add__(self, other) -> "DateVar":
        """
        DateVar + Period following semantics.
        Steps: normalize Y/M, EOM clamp, then add D days in ordinal space.
        """
        if isinstance(other, Period):
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d",
                bounded=self._bounded,
                solver=self._solver
            )
            # Fast-path: only days component (check at Python level since Period components are concrete)
            if other.years == 0 and other.months == 0:
                days_expr = self.days_var + IntVal(other.days)
            else:
                oy, om, od = (
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
                )

                # Decode current date to Y/M/D
                y0, m0, d0 = ymd_from_days_since_epoch(self.days_var)

                # Step 1: Combine Y and M with normalization (carry years)
                period_total_months = oy * IntVal(12) + om
                total_months = m0 + period_total_months
                y1, m1 = normalize_month(y0, total_months)

                # Step 2: EOM clamp
                d1 = eom_clamp(y1, m1, d0)

                if od == 0:
                    # Encode back to days-since-epoch
                    days_expr = days_since_epoch_from_ymd(y1, m1, d1)
                else:
                    # Step 3: add D days in ordinal space
                    days_expr = add_days_ordinal(y1, m1, d1, od)
            
            # Link the computed expression to the result's days_var
            if result._solver is not None:
                result._solver.add(result.days_var == days_expr)
            else:
                # If no solver, just assign directly (for backward compatibility)
                result.days_var = days_expr
            
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


class EpochDaysSolver:
    """Epoch_days date constraint solver using epoch-based conversion."""

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

        # Add constraints for valid date ranges [1900-03-01 to 2100-02-28]
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
            today_days = to_days_since_epoch(Date.from_python_date(today))

            # Calculate ±50 years and ±10 years in days (approximate)
            # Using 365.25 days per year for accuracy
            days_50_years = int(50 * 365.25)
            days_10_years = int(10 * 365.25)

            # Add soft constraints for each date variable
            for name, date_var in self.date_vars.items():
                # High weight: today ± 50 years
                within_50_years = And(
                    date_var.days_var >= IntVal(today_days - days_50_years),
                    date_var.days_var <= IntVal(today_days + days_50_years),
                )
                self.solver.add_soft(within_50_years, weight=100)

                # Low weight: today ± 10 years
                within_10_years = And(
                    date_var.days_var >= IntVal(today_days - days_10_years),
                    date_var.days_var <= IntVal(today_days + days_10_years),
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
