"""
Baseline DATE-SMT implementation using component-based representation.

This module implements the baseline approach where dates are represented
as separate year, month, and day variables, and period arithmetic is done
component-wise with proper normalization.
"""

from typing import Union, Tuple, List
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
    Or,
    Solver,
    sat
)
from ..core import Date, Period

_NONLEAP_PREFIX = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
_LEAP_PREFIX = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
# -------------------------------
# Epoch binding: 2000-03-01
# -------------------------------
# _ORD_EPOCH = to_ordinal(IntVal(2000), IntVal(3), IntVal(1))  # original ground Z3 term
_ORD_EPOCH = IntVal(730179)  # precomputed ordinal of 2000-03-01 (0001-01-01 = 0)

def is_leap(year) -> BoolRef:
    """Check if a year is a leap year."""
    return Or(And(year % 4 == 0, year % 100 != 0), year % 400 == 0)

def days_in_month(year, month) -> ArithRef:
    """Get the number of days in a month, accounting for leap years."""
    return If(
        month == 2,
        If(is_leap(year), 29, 28),
        If(Or(month == 4, month == 6, month == 9, month == 11), 30, 31),
    )

def normalize_month(y, m) -> Tuple[ArithRef, ArithRef]:
    """
    NormMonth(y,m) = (y + ((m-1) div 12), ((m-1) mod 12) + 1)
    Works for concrete and symbolic inputs.
    """
    t = m - 1
    q = t / 12  # Z3 integer division
    r = t % 12  # Z3 modulo
    return y + q, r + 1

def days_before_year(y) -> ArithRef:
    """
    Days from 0001-01-01 to Jan 1 of year y (0-based), Gregorian rules.
    """
    y1 = y - 1
    return 365 * y1 + y1 / 4 - y1 / 100 + y1 / 400

def days_before_month(y, m) -> ArithRef:
    """Z3 piecewise selection (no Python control over symbolic m)."""
    expr = IntVal(0)
    for i in range(1, 13):
        expr = If(m == IntVal(i), _dbm_index(y, i), expr)
    return expr

def to_ordinal(y, m, d) -> ArithRef:
    """Z3-pure ordinal conversion (day 0 = 0001-01-01)."""
    return days_before_year(y) + days_before_month(y, m) + (d - IntVal(1))

def from_ordinal(n) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """Z3-pure ordinal to date conversion using 400/100/4/1 year block decomposition."""
    # 400/100/4/1 year block decomposition
    D400, D100, D4, D1 = IntVal(146097), IntVal(36524), IntVal(1461), IntVal(365)
    q400, r400 = n / D400, n % D400

    q100_raw = r400 / D100
    q100 = If(q100_raw >= IntVal(4), IntVal(3), q100_raw)  # clamp 0..3
    r100 = r400 - q100 * D100

    q4, r4 = r100 / D4, r100 % D4

    q1_raw = r4 / D1
    q1 = If(q1_raw >= IntVal(4), IntVal(3), q1_raw)  # clamp 0..3
    r1 = r4 - q1 * D1  # day-of-year (0..365)

    year = q400 * IntVal(400) + q100 * IntVal(100) + q4 * IntVal(4) + q1 + IntVal(1)

    # month = max i with r1 >= DBM(year, i)
    dbm = [_dbm_index(year, i) for i in range(1, 13)]
    month = IntVal(1)
    for i in range(2, 13):
        month = If(r1 >= dbm[i - 1], IntVal(i), month)

    # day = r1 - DBM(year, month) + 1
    day_expr = r1 - dbm[0] + IntVal(1)
    for i in range(2, 13):
        day_expr = If(r1 >= dbm[i - 1], r1 - dbm[i - 1] + IntVal(1), day_expr)

    return year, month, day_expr

def ymd_from_days_since_epoch(days_term) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """Decode (y,m,d) from a Z3 Int 'days since 2000-03-01'."""
    return from_ordinal(days_term + _ORD_EPOCH)

def days_since_epoch_from_ymd(y, m, d) -> ArithRef:
    """Encode (y,m,d) to Z3 Int 'days since 2000-03-01'."""
    return to_ordinal(y, m, d) - _ORD_EPOCH

def eom_clamp(year, month, day) -> ArithRef:
    """
    End-of-month clamp: ensure day is valid for the given year/month.
    """
    max_day = days_in_month(year, month)
    return If(day < 1, 1, If(day > max_day, max_day, day))

def add_days_ordinal(y, m, d, delta_days) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """
    Exact ordinal-based addition via a single ordinal add.
    Steps:
      - EOM clamp input day (baseline 'round down' policy).
      - If delta_days == 0 → return (y,m,d).
      - Add delta_days in days-since-epoch space and decode.
    """
    # TODO: Can we remove this?
    d0 = eom_clamp(y, m, d)

    # Fast path: no day shift → avoid any ordinal math.
    no_shift = delta_days == IntVal(0)

    # TODO: Use since ordinal directly?
    # Single-step ordinal addition
    z = days_since_epoch_from_ymd(y, m, d0)
    y2, m2, d2 = ymd_from_days_since_epoch(z + delta_days)

    # If delta_days == 0, return (y,m,d0); else the computed (y2,m2,d2)
    out_y = If(no_shift, y, y2)
    out_m = If(no_shift, m, m2)
    out_d = If(no_shift, d0, d2)
    return out_y, out_m, out_d


def _dbm_index(y, idx) -> ArithRef:
    """days_before_month for fixed idx∈{1..12} as a Z3 term."""
    non = IntVal(_NONLEAP_PREFIX[idx - 1])
    lep = IntVal(_LEAP_PREFIX[idx - 1])
    return If(is_leap(y), lep, non)


class DateVar:
    """Symbolic date variable for baseline implementation."""

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Create separate Z3 integer variables for year, month, day
        self.year = Int(f"{name}_year")
        self.month = Int(f"{name}_month")
        self.day = Int(f"{name}_day")

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        year = model.evaluate(self.year, model_completion=True).as_long()
        month = model.evaluate(self.month, model_completion=True).as_long()
        day = model.evaluate(self.day, model_completion=True).as_long()
        return Date(year, month, day)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Or(
                self.year > other.year,
                And(
                    self.year == other.year,
                    Or(
                        self.month > other.month,
                        And(self.month == other.month, self.day >= other.day),
                    ),
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Or(
                self.year < other.year,
                And(
                    self.year == other.year,
                    Or(
                        self.month < other.month,
                        And(self.month == other.month, self.day <= other.day),
                    ),
                ),
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
        if isinstance(other, Date) or isinstance(other, DateVar):
            return And(
                self.year == other.year,
                self.month == other.month,
                self.day == other.day,
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison using ordinal arithmetic."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __add__(self, other) -> 'DateVar':
        """
        DateVar + Period following baseline semantics:
        1) Combine Y and M (normalize months into 1..12 with year carry)
        2) Apply EOM clamp: day := min(original_day, days_in_month(new_year,new_month))
        3) Add D days in ordinal space (exact day arithmetic)
        """
        if isinstance(other, Period):
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
            )

            # Extract period components
            period_years = other.years
            period_months = other.months
            period_days = other.days

            # Step 1: Combine Y and M (normalize months into 1..12 with year carry)
            # Convert period years to months and combine with period months
            period_total_months = period_years * IntVal(12) + period_months
            # Add to current month and normalize
            total_months = self.month + period_total_months
            year_carry, m1 = normalize_month(IntVal(0), total_months)
            y1 = self.year + year_carry

            # Step 2: Apply EOM clamp: day := min(original_day, days_in_month(new_year,new_month))
            d1 = eom_clamp(y1, m1, self.day)

            # Step 3: Add D days in ordinal space (exact day arithmetic)
            y2, m2, d2 = add_days_ordinal(y1, m1, d1, period_days)

            result.year, result.month, result.day = y2, m2, d2
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


class BaselineSolver:
    """Baseline date constraint solver using component-based representation."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with optional year bounds and timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with comprehensive date validation."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Add comprehensive date validation constraints
        # Valid range is 1900-03-01 to 2100-02-28
        self.solver.add(
            Or(
                # 1900-03-01 to 1900-12-31
                And(
                    date_var.year == 1900,
                    date_var.month >= 3,
                    date_var.month <= 12,
                    date_var.day >= 1,
                    date_var.day <= days_in_month(date_var.year, date_var.month),
                ),
                # 1901-01-01 to 2099-12-31
                And(
                    date_var.year >= 1901,
                    date_var.year <= 2099,
                    date_var.month >= 1,
                    date_var.month <= 12,
                    date_var.day >= 1,
                    date_var.day <= days_in_month(date_var.year, date_var.month),
                ),
                # 2100-01-01 to 2100-02-28
                And(
                    date_var.year == 2100,
                    date_var.month >= 1,
                    date_var.month <= 2,
                    date_var.day >= 1,
                    date_var.day <= days_in_month(date_var.year, date_var.month),
                ),
            )
        )

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
