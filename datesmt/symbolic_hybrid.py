"""
Hybrid DATE-SMT implementation using dual representation.

This module implements the hybrid approach where dates are represented
using dual representation: epoch-primary, YMD-derived. Dates are stored
as four Z3 Ints (Y, M, D, E) with a forward link E = to_ordinal(Y,M,D).
Comparisons and day arithmetic use O(1) epoch operations, while month/year
arithmetic uses simple AMI on (Y,M,D) components.
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


def days_in_month_z3(year, month):
    """Z3 expression for days in month (leap-aware)."""
    return If(
        month == 2,
        If(is_leap_year_z3(year), 29, 28),
        If(
            Or(month == 4, month == 6, month == 9, month == 11),
            30,
            31
        )
    )

def is_leap_year_z3(year):
    """Z3 expression for leap year check."""
    return If(
        year % 400 == 0, True,
        If(
            year % 100 == 0, False,
            year % 4 == 0
        )
    )

def days_before_year_z3(year):
    """Z3 expression for days before year (leap-aware)."""
    return 365 * (year - 1) + (year - 1) / 4 - (year - 1) / 100 + (year - 1) / 400

def nonleap_prefix_z3(month):
    """Z3 expression for non-leap year month prefix (0,31,59,90,...,334)."""
    return If(month == 1, 0,
           If(month == 2, 31,
           If(month == 3, 59,
           If(month == 4, 90,
           If(month == 5, 120,
           If(month == 6, 151,
           If(month == 7, 181,
           If(month == 8, 212,
           If(month == 9, 243,
           If(month == 10, 273,
           If(month == 11, 304, 334)))))))))))

def days_before_month_z3(year, month):
    """Z3 expression for days before month (leap-aware, optimized)."""
    # Non-leap prefix + single leap adjustment
    return nonleap_prefix_z3(month) + If(And(is_leap_year_z3(year), month > 2), 1, 0)

def to_ordinal_z3(year, month, day):
    """Z3 expression for ordinal day (leap-aware, optimized)."""
    return days_before_year_z3(year) + days_before_month_z3(year, month) + (day - 1)

class DateVar:
    """
    Symbolic date variable with lazy dual representation.
    
    Uses lazy dual representation: epoch-primary, YMD-derived
    - Primary: epoch_var (always present, used for comparisons and day arithmetic)
    - Secondary: year_var, month_var, day_var (created only when needed)
    - Forward link: Only added when both representations are used
    - Comparisons & day arithmetic: O(1) on epoch_var
    - Month/year arithmetic: Uses YMD vars when available, otherwise creates them
    """

    def __init__(self, ctx, name: str, year_var=None, month_var=None, day_var=None, epoch_var=None):
        """Create a symbolic date variable with lazy dual representation."""
        self.ctx = ctx  # Back-reference to solver context
        self.name = name
        self._forward_link_added = False
        
        if year_var is not None:
            # Created by solver factory with all variables
            self.year_var = year_var
            self.month_var = month_var
            self.day_var = day_var
            self.epoch_var = epoch_var
            self._ymd_vars_exist = True
        else:
            # Legacy constructor - create only epoch variable initially
            self.epoch_var = Int(f"{name}_epoch")
            self._ymd_vars_exist = False
            self._year_var = None
            self._month_var = None
            self._day_var = None
    
    @property
    def days_var(self):
        """Back-compat shim for old code that expects days_var."""
        return self.epoch_var
    
    @property
    def year_var(self):
        """Get year variable, creating YMD vars if needed."""
        if not self._ymd_vars_exist:
            self._ensure_ymd_vars()
        return self._year_var
    
    @property
    def month_var(self):
        """Get month variable, creating YMD vars if needed."""
        if not self._ymd_vars_exist:
            self._ensure_ymd_vars()
        return self._month_var
    
    @property
    def day_var(self):
        """Get day variable, creating YMD vars if needed."""
        if not self._ymd_vars_exist:
            self._ensure_ymd_vars()
        return self._day_var
    
    def _ensure_ymd_vars(self):
        """Create YMD variables and add forward link constraint if not already done."""
        if self._ymd_vars_exist:
            return
            
        # Create YMD variables
        self._year_var = Int(f"{self.name}_year")
        self._month_var = Int(f"{self.name}_month")
        self._day_var = Int(f"{self.name}_day")
        self._ymd_vars_exist = True
        
        # Add calendar validity constraints
        self.ctx._add_date_constraints(self)
        
        # Add forward link constraint
        self._add_forward_link_constraint()
    
    def _add_forward_link_constraint(self):
        """Add the forward link constraint: epoch_var = days_since_epoch_from_ymd(year_var, month_var, day_var)"""
        if self._forward_link_added:
            return
            
        # Add the forward link constraint
        self.ctx.solver.add(
            self.epoch_var == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)
        )
        self._forward_link_added = True

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        if self._ymd_vars_exist:
            # Use YMD variables if they exist
            year = model.evaluate(self._year_var, model_completion=True).as_long()
            month = model.evaluate(self._month_var, model_completion=True).as_long()
            day = model.evaluate(self._day_var, model_completion=True).as_long()
            return Date(year, month, day)
        else:
            # Use epoch variable and convert to Date
            epoch_days = model.evaluate(self.epoch_var, model_completion=True).as_long()
            return from_days_since_epoch(epoch_days)

    def add_forward_link_constraint(self, solver):
        """Add the forward link constraint: E = to_ordinal(Y,M,D)"""
        if hasattr(solver, 'add_constraint'):
            # AdvancedDateSolver
            solver.add_constraint(self.epoch_var == to_ordinal_z3(self.year_var, self.month_var, self.day_var))
        else:
            # Z3 Solver
            solver.add(self.epoch_var == to_ordinal_z3(self.year_var, self.month_var, self.day_var))

    def add_valid_date_constraints(self, solver):
        """Add constraints to ensure valid date representation."""
        if hasattr(solver, 'add_constraint'):
            # AdvancedDateSolver
            solver.add_constraint(self.month_var >= 1)
            solver.add_constraint(self.month_var <= 12)
            solver.add_constraint(self.day_var >= 1)
            solver.add_constraint(self.day_var <= 31)
            
            # Month-specific day constraints
            solver.add_constraint(
                If(
                    self.month_var == 2,
                    If(is_leap_year_z3(self.year_var), self.day_var <= 29, self.day_var <= 28),
                    True,
                )
            )
            
            # 30-day months
            solver.add_constraint(
                If(
                    Or(
                        self.month_var == 4,
                        self.month_var == 6,
                        self.month_var == 9,
                        self.month_var == 11,
                    ),
                    self.day_var <= 30,
                    True,
                )
            )
        else:
            # Z3 Solver
            solver.add(self.month_var >= 1)
            solver.add(self.month_var <= 12)
            solver.add(self.day_var >= 1)
            solver.add(self.day_var <= 31)
            
            # Month-specific day constraints
            solver.add(
                If(
                    self.month_var == 2,
                    If(is_leap_year_z3(self.year_var), self.day_var <= 29, self.day_var <= 28),
                    True,
                )
            )
            
            # 30-day months
            solver.add(
                If(
                    Or(
                        self.month_var == 4,
                        self.month_var == 6,
                        self.month_var == 9,
                        self.month_var == 11,
                    ),
                    self.day_var <= 30,
                    True,
                )
            )

    def __ge__(self, other):
        """Support x >= date comparison using epoch (O(1))."""
        if isinstance(other, Date):
            # Convert concrete date to epoch days and compare
            other_epoch = to_days_since_epoch(other)
            return self.epoch_var >= other_epoch
        elif isinstance(other, DateVar):
            return self.epoch_var >= other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        """Support x <= date comparison using epoch (O(1))."""
        if isinstance(other, Date):
            # Convert concrete date to epoch days and compare
            other_epoch = to_days_since_epoch(other)
            return self.epoch_var <= other_epoch
        elif isinstance(other, DateVar):
            return self.epoch_var <= other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other):
        """Support x < date comparison using epoch (O(1))."""
        if isinstance(other, Date):
            # Convert concrete date to epoch days and compare
            other_epoch = to_days_since_epoch(other)
            return self.epoch_var < other_epoch
        elif isinstance(other, DateVar):
            return self.epoch_var < other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison using epoch (O(1))."""
        if isinstance(other, Date):
            # Convert concrete date to epoch days and compare
            other_epoch = to_days_since_epoch(other)
            return self.epoch_var == other_epoch
        elif isinstance(other, DateVar):
            return self.epoch_var == other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison using epoch (O(1))."""
        return Not(self.__eq__(other))

    def __gt__(self, other):
        """Support x > date comparison using epoch (O(1))."""
        if isinstance(other, Date):
            # Convert concrete date to epoch days and compare
            other_epoch = to_days_since_epoch(other)
            return self.epoch_var > other_epoch
        elif isinstance(other, DateVar):
            return self.epoch_var > other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def shift_days(self, k):
        """Return a new DateVar shifted by k days using epoch arithmetic (O(1))."""
        # Create result through solver factory (auto-registered + constrained)
        import time
        unique_name = f"{self.name}_shift_days_{int(time.time() * 1000000) % 1000000}"
        result = self.ctx.new_date(unique_name)
        k_term = IntVal(k) if isinstance(k, int) else k
        
        # Day arithmetic on epoch (fast)
        self.ctx.solver.add(result.epoch_var == self.epoch_var + k_term)
        
        return result

    def shift_months(self, k, preserve_eom=False):
        """Return a new DateVar shifted by k months using AMI arithmetic."""
        # Create result through solver factory (auto-registered + constrained)
        import time
        unique_name = f"{self.name}_shift_months_{int(time.time() * 1000000) % 1000000}"
        result = self.ctx.new_date(unique_name)
        k_term = IntVal(k) if isinstance(k, int) else k
        
        # Use AMI for month arithmetic (simple and exact)
        ami = 12 * self.year_var + (self.month_var - 1)
        ami_new = ami + k_term
        Yp = ami_new / 12
        Mp = (ami_new % 12) + 1
        
        # EOM handling
        dim_in = days_in_month_z3(self.year_var, self.month_var)
        dim_tp = days_in_month_z3(Yp, Mp)
        eom = (self.day_var == dim_in)
        Dcap = If(self.day_var <= dim_tp, self.day_var, dim_tp)
        Dp = If(preserve_eom, If(eom, dim_tp, Dcap), Dcap)
        
        # Add constraints (no epoch equality - forward link will derive E)
        self.ctx.solver.add([
            result.year_var == Yp,
            result.month_var == Mp,
            result.day_var == Dp
        ])
        
        return result

    def shift_years(self, k, preserve_eom=False):
        """Return a new DateVar shifted by k years using AMI arithmetic."""
        return self.shift_months(12 * k, preserve_eom)

    def shift_period(self, period: Period, preserve_eom=False):
        """Return a new DateVar shifted by a Period using dual representation."""
        # Create result through solver factory (auto-registered + constrained)
        # Use a unique name to avoid conflicts
        import time
        unique_name = f"{self.name}_shift_period_{int(time.time() * 1000000) % 1000000}"
        result = self.ctx.new_date(unique_name)
        
        # Add period arithmetic constraints
        self.ctx.solver.add(self._constraints_for_period(period, result, preserve_eom))
        
        return result

    def _constraints_for_period(self, period: Period, result, preserve_eom=False):
        """Generate constraints for period arithmetic (AMI + day arithmetic)."""
        Y, M, D = self.year_var, self.month_var, self.day_var
        Y2, M2, D2, E2 = result.year_var, result.month_var, result.day_var, result.epoch_var
        
        # AMI arithmetic for months/years
        k = 12 * period.years + period.months
        ami = 12 * Y + (M - 1)
        ami_new = ami + k
        Yp = ami_new / 12
        Mp = (ami_new % 12) + 1
        
        # EOM handling
        dim_in = days_in_month_z3(Y, M)
        dim_tp = days_in_month_z3(Yp, Mp)
        eom = (D == dim_in)
        Dcap = If(D <= dim_tp, D, dim_tp)
        Dp = If(preserve_eom, If(eom, dim_tp, Dcap), Dcap)
        
        # CRITICAL FIX: Use epoch for days-only, YMD for months/years
        if period.years == 0 and period.months == 0:
            # Days only - use epoch arithmetic (perfect for day operations)
            return [E2 == self.epoch_var + IntVal(period.days)]
        elif period.days == 0:
            # Months/years only - use YMD arithmetic (perfect for calendar operations)
            return [Y2 == Yp, M2 == Mp, D2 == Dp]
        else:
            # Mixed: months/years + days - use YMD for calendar part, then add days
            from .symbolic_baseline import add_days_ordinal
            Y2_result, M2_result, D2_result = add_days_ordinal(Yp, Mp, Dp, period.days)
            return [Y2 == Y2_result, M2 == M2_result, D2 == D2_result]

    def __add__(self, other):
        """date + period (exact) or date + PeriodVar (exact)."""
        from .symbolic_hybrid import PeriodVar as _PeriodVar  # avoid cyclic
        if isinstance(other, Period):
            return self.shift_period(other)
        elif isinstance(other, _PeriodVar):
            # For PeriodVar, we need to handle this differently
            # Create result through solver factory (auto-registered + constrained)
            import time
            unique_name = f"{self.name}_plus_period_{int(time.time() * 1000000) % 1000000}"
            result = self.ctx.new_date(unique_name)
            
            # Add constraint: result.epoch_var == self.epoch_var + other.days_var
            self.ctx.solver.add(result.epoch_var == self.epoch_var + other.days_var)
            
            return result
        raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        """date - period (exact) OR date - date ⇒ Int days difference."""
        from .symbolic_hybrid import PeriodVar as _PeriodVar
        if isinstance(other, Period):
            negP = Period(-other.years, -other.months, -other.days)
            return self.shift_period(negP)
        elif isinstance(other, _PeriodVar):
            # For PeriodVar, we need to handle this differently
            # Create result through solver factory (auto-registered + constrained)
            import time
            unique_name = f"{self.name}_minus_period_{int(time.time() * 1000000) % 1000000}"
            result = self.ctx.new_date(unique_name)
            
            # Add constraint: result.epoch_var == self.epoch_var - other.days_var
            self.ctx.solver.add(result.epoch_var == self.epoch_var - other.days_var)
            
            return result
        elif isinstance(other, DateVar):
            # days difference (Z3 Int term)
            return self.diff_days(other)
        elif isinstance(other, Date):
            return self.diff_days(other)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")

    def diff_days(self, other) -> Int:
        """Return Z3 Int: self - other in days."""
        if isinstance(other, DateVar):
            return self.epoch_var - other.epoch_var
        elif isinstance(other, Date):
            other_epoch = to_ordinal(IntVal(other.year), IntVal(other.month), IntVal(other.day)) - _ORD_EPOCH
            return self.epoch_var - other_epoch
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

class HybridDateSolver:
    """Advanced v2 date constraint solver using dual representation (epoch-primary, YMD-derived)."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with dual representation support and timeout.
        
        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def new_date(self, name: str = None) -> DateVar:
        """Create a new DateVar through the solver factory (auto-registered + constrained)."""
        if name is None:
            name = f"d{len(self.date_vars)}"
        
        # Create DateVar with lazy dual representation
        date_var = DateVar(self, name)
        
        # Add to registry
        self.date_vars[name] = date_var
        
        # Add only basic epoch constraints initially
        self._add_basic_epoch_constraints(date_var)
        
        return date_var

    def _add_basic_epoch_constraints(self, date_var: DateVar):
        """Add basic epoch constraints for a DateVar (like advanced approach)."""
        E = date_var.epoch_var
        
        # Add constraints for valid date ranges [1900-01-01 to 2100-12-31]
        # Epoch is March 1, 2000
        # 1900-01-01 to 2000-03-01 = -36584 days
        # 2000-03-01 to 2100-12-31 = +36829 days
        self.solver.add(E >= -36584)  # 1900-01-01
        self.solver.add(E <= 36829)   # 2100-12-31

    def _add_date_constraints(self, date_var: DateVar):
        """Add full constraints for a DateVar when YMD representation is needed."""
        if not date_var._ymd_vars_exist:
            return
            
        Y, M, D, E = date_var._year_var, date_var._month_var, date_var._day_var, date_var.epoch_var
        
        # Year range constraint [1900-2100]
        Y_MIN, Y_MAX = 1900, 2100
        
        # Add calendar validity constraints
        self.solver.add(And(
            1 <= M, M <= 12,
            1 <= D, D <= days_in_month_z3(Y, M),
            Y_MIN <= Y, Y <= Y_MAX
        ))

    def add_date_var(self, name: str) -> DateVar:
        """Legacy method - redirect to new factory."""
        return self.new_date(name)

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
