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
    BitVec,
    BitVecRef,
    BitVecVal,
    BoolRef,
    CheckSatResult,
    If,
    ModelRef,
    Not,
    Optimize,
    Solver,
    sat,
    unsat,
)
from datesat.core import Date, Period
from .bitwidths import LEGACY_BITS
from .simple_bv import (
    eom_clamp,
    normalize_month,
    is_leap
)
# -------------------------------
# Epoch binding: 2000-03-01
# -------------------------------
# _ORD_EPOCH = to_ordinal(BitVecVal(2000, LEGACY_BITS), BitVecVal(3, LEGACY_BITS), BitVecVal(1, LEGACY_BITS))  # original ground Z3 term
_ORD_EPOCH = BitVecVal(
    730179, LEGACY_BITS
)  # precomputed ordinal of 2000-03-01 (0001-01-01 = 0)

_EPOCH = date(2000, 3, 1)

_NONLEAP_PREFIX = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
_LEAP_PREFIX = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]

def date_from_days_since_epoch(days: int) -> Date:
    """Convert concrete days since epoch to a concrete Date."""
    result_date = _EPOCH + timedelta(days=days)
    return Date(result_date.year, result_date.month, result_date.day)

def days_since_epoch_from_date(date_obj: Date) -> int:
    """Convert a concrete Date to concrete days since epoch (March 1, 2000)."""
    target_python = date(date_obj.year, date_obj.month, date_obj.day)
    return (target_python - _EPOCH).days

def add_days_ordinal(y, m, d, delta_days) -> BitVecRef:
    """
    Exact ordinal-based addition via a single ordinal add.
    """
    z = _days_since_epoch_from_ymd_bv(y, m, d)
    return z + delta_days

def days_before_year(y) -> BitVecRef:
    """
    Days from 0001-01-01 to Jan 1 of year y (0-based), Gregorian rules.
    """
    y1 = y - BitVecVal(1, LEGACY_BITS)
    return (
        BitVecVal(365, LEGACY_BITS) * y1
        + y1 / BitVecVal(4, LEGACY_BITS)
        - y1 / BitVecVal(100, LEGACY_BITS)
        + y1 / BitVecVal(400, LEGACY_BITS)
    )

def days_before_month(y, m) -> BitVecRef:
    """Z3 piecewise selection (no Python control over symbolic m)."""
    expr = BitVecVal(0, LEGACY_BITS)
    for i in range(1, 13):
        expr = If(m == BitVecVal(i, LEGACY_BITS), _dbm_index(y, i), expr)
    return expr

def to_ordinal(y, m, d) -> BitVecRef:
    """Z3-pure ordinal conversion (day 0 = 0001-01-01)."""
    return (
        days_before_year(y) + days_before_month(y, m) + (d - BitVecVal(1, LEGACY_BITS))
    )


def from_ordinal(n) -> Tuple[BitVecRef, BitVecRef, BitVecRef]:
    """Z3-pure ordinal to date conversion using 400/100/4/1 year block decomposition."""
    # 400/100/4/1 year block decomposition
    D400, D100, D4, D1 = (
        BitVecVal(146097, LEGACY_BITS),
        BitVecVal(36524, LEGACY_BITS),
        BitVecVal(1461, LEGACY_BITS),
        BitVecVal(365, LEGACY_BITS),
    )
    q400, r400 = n / D400, n % D400

    q100_raw = r400 / D100
    q100 = If(
        q100_raw >= BitVecVal(4, LEGACY_BITS), BitVecVal(3, LEGACY_BITS), q100_raw
    )  # clamp 0..3
    r100 = r400 - q100 * D100

    q4, r4 = r100 / D4, r100 % D4

    q1_raw = r4 / D1
    q1 = If(
        q1_raw >= BitVecVal(4, LEGACY_BITS), BitVecVal(3, LEGACY_BITS), q1_raw
    )  # clamp 0..3
    r1 = r4 - q1 * D1  # day-of-year (0..365)

    year = (
        q400 * BitVecVal(400, LEGACY_BITS)
        + q100 * BitVecVal(100, LEGACY_BITS)
        + q4 * BitVecVal(4, LEGACY_BITS)
        + q1
        + BitVecVal(1, LEGACY_BITS)
    )

    # month = max i with r1 >= DBM(year, i)
    dbm = [_dbm_index(year, i) for i in range(1, 13)]
    month = BitVecVal(1, LEGACY_BITS)
    for i in range(2, 13):
        month = If(r1 >= dbm[i - 1], BitVecVal(i, LEGACY_BITS), month)

    # day = r1 - DBM(year, month) + 1
    day_expr = r1 - dbm[0] + BitVecVal(1, LEGACY_BITS)
    for i in range(2, 13):
        day_expr = If(
            r1 >= dbm[i - 1], r1 - dbm[i - 1] + BitVecVal(1, LEGACY_BITS), day_expr
        )

    return year, month, day_expr

def _ymd_from_days_since_epoch_bv(days_term: BitVecRef) -> Tuple[BitVecRef, BitVecRef, BitVecRef]:
    """Decode (y,m,d) from a Z3 BitVec 'days since 2000-03-01'."""
    return from_ordinal(days_term + _ORD_EPOCH)

def _days_since_epoch_from_ymd_bv(y: BitVecRef, m: BitVecRef, d: BitVecRef) -> BitVecRef:
    """Encode (y,m,d) to Z3 BitVec 'days since 2000-03-01'."""
    return to_ordinal(y, m, d) - _ORD_EPOCH

def ymd_from_days_since_epoch(days_term):
    """
    Overload:
    - ymd_from_days_since_epoch(int) -> Date
    - ymd_from_days_since_epoch(BitVecRef) -> (y,m,d) BitVecRefs
    """
    if isinstance(days_term, int):
        return date_from_days_since_epoch(days_term)
    return _ymd_from_days_since_epoch_bv(days_term)

def days_since_epoch_from_ymd(*args):
    """
    Overload:
    - days_since_epoch_from_ymd(Date) -> int
    - days_since_epoch_from_ymd(y,m,d) -> BitVecRef
    """
    if len(args) == 1 and isinstance(args[0], Date):
        return days_since_epoch_from_date(args[0])
    if len(args) == 3:
        y, m, d = args
        return _days_since_epoch_from_ymd_bv(y, m, d)
    raise TypeError("days_since_epoch_from_ymd expects (Date) or (y, m, d)")

def _dbm_index(y, idx) -> BitVecRef:
    """days_before_month for fixed idx∈{1..12} as a Z3 term."""
    non = BitVecVal(_NONLEAP_PREFIX[idx - 1], LEGACY_BITS)
    lep = BitVecVal(_LEAP_PREFIX[idx - 1], LEGACY_BITS)
    return If(is_leap(y), lep, non)

class DateVar:
    """Symbolic date variable for epoch_days implementation."""

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Use a single Z3 bitvector variable for days since epoch
        self.days_var = BitVec(f"{name}_days", LEGACY_BITS)
        # Solver reference for adding bounds to intermediate dates (set after creation if needed)
        self._solver = None

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    @property
    def year(self) -> BitVecRef:
        """Get symbolic year component (decodes from days_var)."""
        y, _, _ = ymd_from_days_since_epoch(self.days_var)
        return y

    @property
    def month(self) -> BitVecRef:
        """Get symbolic month component (decodes from days_var)."""
        _, m, _ = ymd_from_days_since_epoch(self.days_var)
        return m

    @property
    def day(self) -> BitVecRef:
        """Get symbolic day component (decodes from days_var)."""
        _, _, d = ymd_from_days_since_epoch(self.days_var)
        return d

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        days = model.evaluate(self.days_var, model_completion=True).as_signed_long()
        return date_from_days_since_epoch(days)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            return self.days_var >= BitVecVal(days_since_epoch_from_date(other), LEGACY_BITS)
        elif isinstance(other, DateVar):
            return self.days_var >= other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            return self.days_var <= BitVecVal(days_since_epoch_from_date(other), LEGACY_BITS)
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
            return self.days_var == BitVecVal(days_since_epoch_from_date(other), LEGACY_BITS)
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
        self._solver.add(self.days_var >= BitVecVal(-36525, LEGACY_BITS))
        self._solver.add(self.days_var <= BitVecVal(36523, LEGACY_BITS))

    def __add__(self, other) -> "DateVar":
        """
        DateVar + Period following semantics.
        Steps: normalize Y/M, EOM clamp, then add D days in ordinal space.
        """
        if isinstance(other, Period):
            result = DateVar(f"{self.name}_plus")
            
            # Fast-path: only days component (check at Python level since Period components are concrete)
            if other.years == 0 and other.months == 0:
                days_expr = self.days_var + BitVecVal(other.days, LEGACY_BITS)
            else:
                oy, om, od = (
                    BitVecVal(other.years, LEGACY_BITS),
                    BitVecVal(other.months, LEGACY_BITS),
                    BitVecVal(other.days, LEGACY_BITS),
                )

                # Decode current date to Y/M/D
                y0, m0, d0 = ymd_from_days_since_epoch(self.days_var)

                # Step 1: Combine Y and M with normalization (carry years)
                period_total_months = oy * BitVecVal(12, LEGACY_BITS) + om
                total_months = m0 + period_total_months
                y1, m1 = normalize_month(y0, total_months)

                # Step 2: EOM clamp
                d1 = eom_clamp(y1, m1, d0)

                if other.days == 0:
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
                    date_var.days_var
                    >= BitVecVal(today_days - days_50_years, LEGACY_BITS),
                    date_var.days_var
                    <= BitVecVal(today_days + days_50_years, LEGACY_BITS),
                )
                self.solver.add_soft(within_50_years, weight=100)

                # Low weight: today ± 10 years
                within_10_years = And(
                    date_var.days_var
                    >= BitVecVal(today_days - days_10_years, LEGACY_BITS),
                    date_var.days_var
                    <= BitVecVal(today_days + days_10_years, LEGACY_BITS),
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
