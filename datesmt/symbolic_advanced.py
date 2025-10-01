"""
Advanced DATE-SMT implementation using epoch-based conversion.

This module implements the advanced approach where dates are represented
as days since an epoch, and period arithmetic is done using approximate
day conversions.
"""

from typing import Union

from z3 import (
    And,
    BoolRef,
    CheckSatResult,
    If,
    Int,
    IntVal,
    ModelRef,
    Not,
    Or,
    Solver,
    sat,
    unsat,
)

from .core import Date, Period


def from_days_since_epoch(days: int) -> Date:
    """Convert days since epoch to a Date using a more robust approach."""
    # March 1, 2000 is day 0

    # Use Python's datetime for accurate date arithmetic
    from datetime import date, timedelta

    # Convert our epoch to Python date
    epoch_python = date(2000, 3, 1)

    # Add the days
    result_python = epoch_python + timedelta(days=days)

    # Convert back to our Date class
    return Date(result_python.year, result_python.month, result_python.day)


def to_days_since_epoch(date_obj: Date) -> int:
    """Convert a Date to days since epoch (March 1, 2000) using a more robust approach."""
    # March 1, 2000 is day 0

    # Use Python's datetime for accurate date arithmetic
    from datetime import date, timedelta

    # Convert to Python dates
    epoch_python = date(2000, 3, 1)
    target_python = date(date_obj.year, date_obj.month, date_obj.day)

    # Calculate the difference
    delta = target_python - epoch_python
    return delta.days


def is_leap_year(year: int) -> bool:
    """Check if a year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """Get the number of days in a month."""
    if month == 2:
        return 29 if is_leap_year(year) else 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return 31


def to_days_approximate(period: Period) -> int:
    """Convert a Period to approximate days for Z3 constraints."""
    # Simple approximation - not accurate for real calendar arithmetic
    return period.years * 365 + period.months * 30 + period.days


def to_days_with_context(period: Period, reference_date: Date) -> int:
    """
    Convert a Period to exact days based on a reference date context.

    This function calculates the actual number of days for a period by:
    1. Converting the reference date to days since epoch
    2. Simulating the period addition using proper calendar arithmetic
    3. Converting the result back to days since epoch
    4. Returning the difference

    Args:
        period: The period to convert (years, months, days)
        reference_date: The starting date to calculate from

    Returns:
        int: The exact number of days for the period in the given context
    """
    # Convert reference date to days since epoch
    start_days = to_days_since_epoch(reference_date)

    # For simple cases (days only), return directly
    if period.years == 0 and period.months == 0:
        return period.days

    # For complex cases, we need to use the from_days_since_epoch approach
    # but with careful handling of calendar arithmetic

    # Calculate the target date by applying the period
    target_year = reference_date.year + period.years
    target_month = reference_date.month + period.months
    target_day = reference_date.day + period.days

    # Normalize the month and year
    while target_month > 12:
        target_year += 1
        target_month -= 12
    while target_month < 1:
        target_year -= 1
        target_month += 12

    # Handle day overflow/underflow
    max_day = days_in_month(target_year, target_month)
    if target_day > max_day:
        # Day overflow - clamp to end of month
        target_day = max_day
    elif target_day < 1:
        # Day underflow - go to previous month
        target_month -= 1
        if target_month < 1:
            target_year -= 1
            target_month = 12
        max_day_prev = days_in_month(target_year, target_month)
        target_day = max_day_prev + target_day

    # Create the target date and convert to days since epoch
    try:
        target_date = Date(target_year, target_month, target_day)
        end_days = to_days_since_epoch(target_date)
        return end_days - start_days
    except ValueError:
        # Fallback to approximation if date construction fails
        return to_days_approximate(period)


def to_days_smart(period: Period, reference_date: Date = None) -> int:
    """
    Convert a Period to days using context-aware calculation when possible.

    Args:
        period: The period to convert
        reference_date: Optional reference date for context-aware calculation

    Returns:
        int: Number of days (exact if reference_date provided, approximate otherwise)
    """
    if reference_date is not None:
        return to_days_with_context(period, reference_date)
    else:
        # Fall back to approximation when no context is available
        return to_days_approximate(period)


def to_z3_constraint(date: Date) -> int:
    """Convert a Date to Z3 integer constraint."""
    return to_days_since_epoch(date)


# -------------------------------
# Z3-pure calendar helpers (exact)
# -------------------------------

def is_leap_year_z3(y):
    """Z3-pure leap year check."""
    return Or(And(y % 4 == 0, y % 100 != 0), y % 400 == 0)


def days_in_month_z3(y, m):
    """Z3-pure days in month calculation."""
    return If(
        m == 2,
        If(is_leap_year_z3(y), IntVal(29), IntVal(28)),
        If(Or(m == 4, m == 6, m == 9, m == 11), IntVal(30), IntVal(31)),
    )


def normalize_month(y, m):
    """Z3-pure month normalization (1..12)."""
    t = m - IntVal(1)
    q = t / IntVal(12)          # Z3 integer division
    r = t % IntVal(12)          # Z3 modulo
    return y + q, r + IntVal(1)


# -------------------------------
# Ordinal (0001-01-01 is day 0)
# -------------------------------
_NONLEAP_PREFIX = [0,31,59,90,120,151,181,212,243,273,304,334]
_LEAP_PREFIX    = [0,31,60,91,121,152,182,213,244,274,305,335]


def _dbm_idx(y, idx):
    """Helper for days before month calculation."""
    non = IntVal(_NONLEAP_PREFIX[idx-1])
    lep = IntVal(_LEAP_PREFIX[idx-1])
    return If(is_leap_year_z3(y), lep, non)


def days_before_year(y):
    """Z3-pure days before year calculation."""
    y1 = y - IntVal(1)
    return IntVal(365) * y1 + y1 / IntVal(4) - y1 / IntVal(100) + y1 / IntVal(400)


def days_before_month(y, m):
    """Z3-pure days before month calculation."""
    expr = IntVal(0)
    for i in range(1, 13):
        expr = If(m == IntVal(i), _dbm_idx(y, i), expr)
    return expr


def to_ordinal(y, m, d):
    """Z3-pure ordinal conversion (day 0 = 0001-01-01)."""
    return days_before_year(y) + days_before_month(y, m) + (d - IntVal(1))


def from_ordinal(n):
    """Z3-pure ordinal to date conversion using 400/100/4/1 year block decomposition."""
    # 400/100/4/1 year block decomposition
    D400, D100, D4, D1 = IntVal(146097), IntVal(36524), IntVal(1461), IntVal(365)
    q400, r400 = n / D400, n % D400

    q100_raw = r400 / D100
    q100     = If(q100_raw >= IntVal(4), IntVal(3), q100_raw)    # clamp 0..3
    r100     = r400 - q100 * D100

    q4, r4   = r100 / D4, r100 % D4

    q1_raw = r4 / D1
    q1     = If(q1_raw >= IntVal(4), IntVal(3), q1_raw)          # clamp 0..3
    r1     = r4 - q1 * D1                                        # day-of-year (0..365)

    year = q400 * IntVal(400) + q100 * IntVal(100) + q4 * IntVal(4) + q1 + IntVal(1)

    # month = max i with r1 >= DBM(year, i)
    dbm = [_dbm_idx(year, i) for i in range(1, 13)]
    month = IntVal(1)
    for i in range(2, 13):
        month = If(r1 >= dbm[i-1], IntVal(i), month)

    # day = r1 - DBM(year, month) + 1
    day_expr = r1 - dbm[0] + IntVal(1)
    for i in range(2, 13):
        day_expr = If(r1 >= dbm[i-1], r1 - dbm[i-1] + IntVal(1), day_expr)

    return year, month, day_expr


# -------------------------------
# Epoch binding: 2000-03-01
# -------------------------------
_ORD_EPOCH = to_ordinal(IntVal(2000), IntVal(3), IntVal(1))  # a ground Z3 term


def ymd_from_days_since_epoch(days_term):
    """Decode (y,m,d) from a Z3 Int 'days since 2000-03-01'."""
    return from_ordinal(days_term + _ORD_EPOCH)


def days_since_epoch_from_ymd(y, m, d):
    """Encode (y,m,d) to Z3 Int 'days since 2000-03-01'."""
    return to_ordinal(y, m, d) - _ORD_EPOCH


def eom_clamp(y, m, d):
    """Z3-pure end-of-month clamping."""
    maxd = days_in_month_z3(y, m)
    return If(d < IntVal(1), IntVal(1), If(d > maxd, maxd, d))


FOUR_HUNDRED_YEARS = IntVal(146097)  # 400*365 + 97 leap days

def add_days_ordinal(y, m, d, delta_days):
    """
    Exact ordinal-based addition with 400-year cycle reduction.
    Steps:
      - EOM clamp input day (baseline 'round down' policy).
      - If delta_days == 0 → return (y,m,d).
      - Split delta_days into q*146097 + r. Add 400*q years first (no month change),
        then add the small remainder r via ordinal transform.
    """
    d0 = eom_clamp(y, m, d)

    # Fast path: no day shift → avoid any ordinal math.
    no_shift = (delta_days == IntVal(0))
    y_ns, m_ns, d_ns = y, m, d0

    # Reduce by 400-year eras to keep terms small
    q = delta_days / FOUR_HUNDRED_YEARS
    r = delta_days % FOUR_HUNDRED_YEARS

    # Shift whole eras in the year; month/day unchanged for this step
    y_era = y + q * IntVal(400)

    # Now add the small remainder r via ordinal conversion
    z   = days_since_epoch_from_ymd(y_era, m, d0)
    z2  = z + r
    y2, m2, d2 = ymd_from_days_since_epoch(z2)

    # If delta_days == 0, return (y,m,d0); else the computed (y2,m2,d2)
    out_y = If(no_shift, y_ns, y2)
    out_m = If(no_shift, m_ns, m2)
    out_d = If(no_shift, d_ns, d2)
    return out_y, out_m, out_d

def add_period_exact_days(days_term, period):
    """
    Given current 'days since epoch' (Z3 Int) and a concrete Period,
    return the exact resulting 'days since epoch' (Z3 Int) under EOM policy:
    1) add (Y,M) with NormMonth
    2) EOM clamp the day
    3) add D days in ordinal space
    """
    y, m, d = ymd_from_days_since_epoch(days_term)

    # 1) months/years
    y2, m2 = normalize_month(y + IntVal(period.years), m + IntVal(period.months))

    # 2) EOM clamp
    d2 = eom_clamp(y2, m2, d)

    # 3) add D days in ordinal space
    base_ord = to_ordinal(y2, m2, d2)
    new_ord  = base_ord + IntVal(period.days)

    # encode back to days since epoch
    return new_ord - _ORD_EPOCH


class DateVar:
    """Symbolic date variable for advanced implementation."""

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Use a single Z3 integer variable for days since epoch
        self.days_var = Int(f"{name}_days")

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        days = model.evaluate(self.days_var, model_completion=True).as_long()
        return from_days_since_epoch(days)

    def __ge__(self, other):
        """Support x >= date comparison."""
        if isinstance(other, Date):
            return self.days_var >= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var >= other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        """Support x <= date comparison."""
        if isinstance(other, Date):
            return self.days_var <= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var <= other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other):
        """Support x < date comparison."""
        if isinstance(other, Date):
            return self.days_var < to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var < other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison."""
        if isinstance(other, Date):
            return self.days_var == to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var == other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison."""
        return Not(self.__eq__(other))

    def __gt__(self, other):
        """Support x > date comparison."""
        if isinstance(other, Date):
            return self.days_var > to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.days_var > other.days_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def shift_days(self, k):
        """Return a new DateVar shifted by k (Z3 Int or int) days (exact)."""
        result = DateVar(f"{self.name}_shift_{k}")
        k_term = IntVal(k) if isinstance(k, int) else k
        result.days_var = self.days_var + k_term
        return result

    def __add__(self, other):
        """date + period (exact) or date + PeriodVar (exact)."""
        from .symbolic_advanced import PeriodVar as _PeriodVar  # avoid cyclic
        if isinstance(other, Period):
            out = DateVar(f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d")
            out.days_var = add_period_exact_days(self.days_var, other)
            return out
        elif isinstance(other, _PeriodVar):
            out = DateVar(f"{self.name}_plus_{other.name}")
            out.days_var = self.days_var + other.days_var
            return out
        raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        """date - period (exact) OR date - date ⇒ Int days difference."""
        from .symbolic_advanced import PeriodVar as _PeriodVar
        if isinstance(other, Period):
            negP = Period(-other.years, -other.months, -other.days)
            out = DateVar(f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d")
            out.days_var = add_period_exact_days(self.days_var, negP)
            return out
        elif isinstance(other, _PeriodVar):
            out = DateVar(f"{self.name}_minus_{other.name}")
            out.days_var = self.days_var - other.days_var
            return out
        elif isinstance(other, DateVar):
            # days difference (Z3 Int term)
            return self.days_var - other.days_var
        elif isinstance(other, Date):
            return self.days_var - IntVal(to_days_since_epoch(other))
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")

    def diff_days(self, other) -> Int:
        """Return Z3 Int: self - other in days."""
        if isinstance(other, DateVar):
            return self.days_var - other.days_var
        elif isinstance(other, Date):
            return self.days_var - IntVal(to_days_since_epoch(other))
        else:
            raise TypeError("diff_days expects DateVar or Date")


class PeriodVar:
    """Symbolic period variable for advanced implementation."""

    def __init__(self, name: str):
        """Create a symbolic period variable."""
        self.name = name
        # Use a single Z3 integer variable for approximate days
        self.days_var = Int(f"{name}_days")

    def __str__(self):
        return f"PeriodVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_period(self, model: ModelRef) -> Period:
        """Convert Z3 model to concrete Period."""
        days = model.evaluate(self.days_var, model_completion=True).as_long()
        # Simple approximation - not accurate for real calendar arithmetic
        years = days // 365
        months = (days % 365) // 30
        remaining_days = days % 30
        return Period(years, months, remaining_days)

    def to_days_approximate(self) -> int:
        """Convert to approximate days for Z3 constraints."""
        return self.days_var

    def __eq__(self, other):
        """Support equality with concrete Period or another PeriodVar."""
        if isinstance(other, Period):
            return self.days_var == to_days_approximate(other)
        elif isinstance(other, PeriodVar):
            return self.days_var == other.days_var
        else:
            raise TypeError(f"Cannot compare PeriodVar with {type(other)}")

    def __ne__(self, other):
        """Support inequality with concrete Period or another PeriodVar."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        if isinstance(other, PeriodVar):
            out = PeriodVar(f"{self.name}_plus_{other.name}")
            out.days_var = self.days_var + other.days_var
            return out
        elif isinstance(other, Period):
            out = PeriodVar(f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d")
            out.days_var = self.days_var + IntVal(to_days_approximate(other))  # or leave blocked
            return out
        raise TypeError(f"Cannot add {type(other)} to PeriodVar")

    def __sub__(self, other):
        if isinstance(other, PeriodVar):
            out = PeriodVar(f"{self.name}_minus_{other.name}")
            out.days_var = self.days_var - other.days_var
            return out
        elif isinstance(other, Period):
            out = PeriodVar(f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d")
            out.days_var = self.days_var - IntVal(to_days_approximate(other))
            return out
        raise TypeError(f"Cannot subtract {type(other)} from PeriodVar")

    def __mul__(self, k):
        if isinstance(k, int):
            out = PeriodVar(f"{self.name}_times_{k}")
            out.days_var = self.days_var * IntVal(k)
            return out
        raise TypeError(f"Cannot multiply PeriodVar by {type(k)}")

    def __rmul__(self, k):
        return self.__mul__(k)


class AdvancedDateSolver:
    """Advanced date constraint solver using epoch-based conversion."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with timeout.
        
        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Add constraints for valid date ranges [1900-01-01 to 2100-12-31]
        # Epoch is March 1, 2000
        # 1900-01-01 to 2000-03-01 = -36584 days
        # 2000-03-01 to 2100-12-31 = +36829 days
        self.solver.add(date_var.days_var >= -36584)  # 1900-01-01
        self.solver.add(date_var.days_var <= 36829)   # 2100-12-31

        return date_var

    def add_period_var(self, name: str) -> PeriodVar:
        """Add a symbolic period variable."""
        period_var = PeriodVar(name)
        self.period_vars[name] = period_var
        return period_var

    def add_constraint(self, constraint: BoolRef):
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

    def get_concrete_periods(self, model: ModelRef) -> dict:
        """Get concrete periods from the model."""
        return {
            name: var.to_concrete_period(model)
            for name, var in self.period_vars.items()
        }

    def solve(self) -> Union[bool, dict]:
        """Solve the constraints."""
        result = self.check()
        if result == sat:
            model = self.model()
            return {
                'status': 'sat',
                'dates': self.get_concrete_dates(model),
                'periods': self.get_concrete_periods(model),
            }
        else:
            return {'status': 'unsat', 'dates': {}, 'periods': {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self):
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())

    def add_accurate_period_constraint(
        self, date_var: DateVar, period: Period, result_var: DateVar
    ):
        """
        Add a constraint for accurate period arithmetic.

        This method attempts to create more accurate constraints for period arithmetic
        by considering multiple possible calendar contexts. While not as accurate as
        the baseline approach, it's better than pure approximation.

        Args:
            date_var: The starting date variable
            period: The period to add
            result_var: The resulting date variable after adding the period
        """
        if period.years == 0 and period.months == 0:
            # Simple case: only days, this is exact
            self.add_constraint(result_var.days_var == date_var.days_var + period.days)
        else:
            # Complex case: approximate but add bounds for more accuracy
            approx_days = to_days_approximate(period)

            # Add the approximate constraint
            self.add_constraint(result_var.days_var == date_var.days_var + approx_days)

            # Add bounds to constrain the error
            # Years: 365-366 days each, Months: 28-31 days each
            min_year_days = period.years * 365
            max_year_days = period.years * 366
            min_month_days = period.months * 28
            max_month_days = period.months * 31

            min_total = min_year_days + min_month_days + period.days
            max_total = max_year_days + max_month_days + period.days

            # These constraints help bound the approximation error
            # Not perfect, but better than unlimited approximation
            self.add_constraint(result_var.days_var >= date_var.days_var + min_total)
            self.add_constraint(result_var.days_var <= date_var.days_var + max_total)

    def add_exact_period_constraint(
        self, concrete_date: Date, period: Period, result_var: DateVar
    ):
        """
        Add an exact period arithmetic constraint when the starting date is concrete.

        This method calculates the exact number of days for the period based on the
        concrete starting date, providing accurate calendar arithmetic.

        Args:
            concrete_date: The concrete starting date
            period: The period to add
            result_var: The resulting date variable
        """
        exact_days = to_days_with_context(period, concrete_date)
        concrete_start_days = to_days_since_epoch(concrete_date)

        self.add_constraint(result_var.days_var == concrete_start_days + exact_days)

    def add_exact_period_constraint_var(
        self, start: DateVar, period: Period, out: DateVar
    ):
        """Exact constraint for DateVar + concrete Period using the Z3-pure EOM+ordinal pipeline."""
        self.add_constraint(out.days_var == add_period_exact_days(start.days_var, period))
