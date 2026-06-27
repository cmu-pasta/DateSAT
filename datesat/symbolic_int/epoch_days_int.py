"""
Epoch_days DateSAT implementation using epoch-based conversion.

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
    Solver,
    sat,
    unsat,
)
from ..core import Date, Period
from .simple_int import (
    eom_clamp,
    normalize_month
)

_EPOCH = date(2000, 3, 1)

def _ymd_from_days_since_epoch_z3(days_term: ArithRef) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """
    Decode (y,m,d) from a Z3 Int 'days since 2000-03-01', directly.

    Uses March-based civil-from-days arithmetic anchored at 2000-03-01, which is:
      - the start of a March-based year, and
      - in year 2000, which is divisible by 400 (cycle boundary).
    So we can do pure 400/100/4/1 block decomposition + a constant-time month/day formula.
    """
    # Constants
    D400, D100, D4, D1 = IntVal(146097), IntVal(36524), IntVal(1461), IntVal(365)

    # Split into 400-year cycles (Z3 div/mod with positive divisor gives 0 <= r < D400 even for negative days_term)
    q400, r400 = days_term / D400, days_term % D400

    # 100-year blocks within the 400-year cycle (clamp the last block)
    q100_raw = r400 / D100
    q100 = If(q100_raw >= IntVal(4), IntVal(3), q100_raw)  # 0..3
    r100 = r400 - q100 * D100

    # 4-year blocks
    q4, r4 = r100 / D4, r100 % D4

    # 1-year blocks (clamp the last block)
    q1_raw = r4 / D1
    q1 = If(q1_raw >= IntVal(4), IntVal(3), q1_raw)  # 0..3
    r1 = r4 - q1 * D1  # day-of-year in March-based year, 0..365

    # March-based year (starts at Mar 1). Day 0 == 2000-03-01.
    y = IntVal(2000) + q400 * IntVal(400) + q100 * IntVal(100) + q4 * IntVal(4) + q1

    # Convert March-based day-of-year to month/day using 153-day month blocks
    # mp: 0..11 corresponds to Mar..Feb
    mp = (IntVal(5) * r1 + IntVal(2)) / IntVal(153)
    d  = r1 - (IntVal(153) * mp + IntVal(2)) / IntVal(5) + IntVal(1)

    m  = mp + IntVal(3)                 # Mar=3,...,Dec=12,Jan=13,Feb=14
    m  = If(m > IntVal(12), m - IntVal(12), m)  # wrap Jan/Feb back to 1/2

    # If month is Jan/Feb, it belongs to the next Gregorian year
    y  = y + If(m <= IntVal(2), IntVal(1), IntVal(0))

    return y, m, d

_EPOCH_MARCH_BASED_ABS = IntVal(730485)  # days_from_civil(2000,3,1) in March-based absolute days

def _days_since_epoch_from_ymd_z3(y: ArithRef, m: ArithRef, d: ArithRef) -> ArithRef:
    D400 = IntVal(146097)

    # Shift Jan/Feb into previous year to make Mar the first month
    y_adj = y - If(m <= IntVal(2), IntVal(1), IntVal(0))
    m_adj = m + If(m <= IntVal(2), IntVal(12), IntVal(0))  # now 3..14
    mp = m_adj - IntVal(3)  # 0..11 (Mar..Feb)

    # 400-year era decomposition (Z3 div is Euclidean for positive divisor)
    era = y_adj / IntVal(400)
    yoe = y_adj - era * IntVal(400)  # 0..399 (within era)

    # Day-of-year within March-based year
    doy = (IntVal(153) * mp + IntVal(2)) / IntVal(5) + (d - IntVal(1))  # 0..365

    # Day-of-era: days from start of era to start of year yoe
    # Formula: yoe * 365 + yoe/4 - yoe/100 + yoe/400
    # This accounts for leap years: every 4 years, except centuries, except 400-year cycles
    doe = yoe * IntVal(365) + (yoe / IntVal(4)) - (yoe / IntVal(100)) + (yoe / IntVal(400)) + doy

    # Absolute days since 0000-03-01, then shift so 2000-03-01 is 0
    abs_days = era * D400 + doe
    return abs_days - _EPOCH_MARCH_BASED_ABS


def ymd_from_days_since_epoch(days_term):
    """
    Overload:
    - ymd_from_days_since_epoch(int) -> Date
    - ymd_from_days_since_epoch(ArithRef) -> (y,m,d) ArithRefs
    """
    if isinstance(days_term, int):
        return date_from_days_since_epoch(days_term)
    return _ymd_from_days_since_epoch_z3(days_term)


def days_since_epoch_from_ymd(*args):
    """
    Overload:
    - days_since_epoch_from_ymd(Date) -> int
    - days_since_epoch_from_ymd(y,m,d) -> ArithRef
    """
    if len(args) == 1 and isinstance(args[0], Date):
        return days_since_epoch_from_date(args[0])
    if len(args) == 3:
        y, m, d = args
        return _days_since_epoch_from_ymd_z3(y, m, d)
    raise TypeError("days_since_epoch_from_ymd expects (Date) or (y, m, d)")

def date_from_days_since_epoch(days: int) -> Date:
    """Convert concrete days since epoch to a concrete Date."""
    result_date = _EPOCH + timedelta(days=days)
    return Date(result_date.year, result_date.month, result_date.day)


def days_since_epoch_from_date(date_obj: Date) -> int:
    """Convert a concrete Date to concrete days since epoch (March 1, 2000)."""
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

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Use a single Z3 integer variable for days since epoch
        self.days_var = Int(f"{name}_days")
        # Solver reference for adding bounds to intermediate dates (set after creation if needed)
        self._solver = None

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
        return date_from_days_since_epoch(days)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            return self.days_var >= days_since_epoch_from_date(other)
        elif isinstance(other, DateVar):
            return self.days_var >= other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            return self.days_var <= days_since_epoch_from_date(other)
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
            return self.days_var == days_since_epoch_from_date(other)
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
        """Add date validation bounds to this DateVar if solver is available."""
        if self._solver is None:
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
            result = DateVar(f"{self.name}_plus")
            
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
            
            # Direct assignment 
            result.days_var = days_expr
            
            # Add bounds to intermediate result
            result._solver = self._solver
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
        date_var = DateVar(name)
        date_var._solver = self.solver
        self.date_vars[name] = date_var

        # Add bounds using _add_bounds method
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
            today_days = days_since_epoch_from_date(Date.from_python_date(today))

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
