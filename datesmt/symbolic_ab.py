"""
Alpha-beta DATE-SMT implementation using epoch-based conversion.

This module implements the alpha-beta approach where dates are represented
as (months, days) since an epoch.
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


# -------------------------------
# Z3-pure calendar helpers
# -------------------------------


def is_leap_year(y):
    """Z3-pure leap year check."""
    return Or(And(y % 4 == 0, y % 100 != 0), y % 400 == 0)


def days_in_month(y, m):
    """Z3-pure days in month calculation."""
    return If(
        m == 2,
        If(is_leap_year(y), IntVal(29), IntVal(28)),
        If(Or(m == 4, m == 6, m == 9, m == 11), IntVal(30), IntVal(31)),
    )


# -------------------------------
# Ordinal (0001-01-01 is day 0)
# -------------------------------
_NONLEAP_PREFIX = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
_LEAP_PREFIX = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]


def _dbm_index(y, idx):
    """Helper for days before month calculation."""
    non = IntVal(_NONLEAP_PREFIX[idx - 1])
    lep = IntVal(_LEAP_PREFIX[idx - 1])
    return If(is_leap_year(y), lep, non)


def days_before_year(y):
    """Z3-pure days before year calculation."""
    y1 = y - IntVal(1)
    return IntVal(365) * y1 + y1 / IntVal(4) - y1 / IntVal(100) + y1 / IntVal(400)


def days_before_month(y, m):
    """Z3-pure days before month calculation."""
    expr = IntVal(0)
    for i in range(1, 13):
        expr = If(m == IntVal(i), _dbm_index(y, i), expr)
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


# -------------------------------
# Epoch binding: 2000-03-01
# -------------------------------
# _ORD_EPOCH = to_ordinal(IntVal(2000), IntVal(3), IntVal(1))  # original ground Z3 term
_ORD_EPOCH = IntVal(730179)  # precomputed ordinal of 2000-03-01 (0001-01-01 = 0)


def ymd_from_days_since_epoch(days_term):
    """Decode (y,m,d) from a Z3 Int 'days since 2000-03-01'."""
    return from_ordinal(days_term + _ORD_EPOCH)


def days_since_epoch_from_ymd(y, m, d):
    """Encode (y,m,d) to Z3 Int 'days since 2000-03-01'."""
    return to_ordinal(y, m, d) - _ORD_EPOCH


# -------------------------------
# Alpha (months-since-epoch) helpers
# Epoch month: 2000-03 (alpha = 0)
# alpha = 12*y + m - (12*2000 + 3)
# Inverse: let k = alpha + (12*2000 + 3), then
#   y = (k - 1) / 12
#   m = k - 12*y
# -------------------------------
# Python int epoch constants (for arithmetic outside Z3)
EPOCH_YEAR = 2000
EPOCH_MONTH = 3
# Z3 epoch constants
_EPOCH_LINEAR = EPOCH_YEAR * 12 + EPOCH_MONTH  # 12*2000 + 3


def months_since_epoch_from_ym(y, m):
    """Z3-pure: compute months-since-epoch (alpha) from year/month."""
    return (y * 12 + m) - _EPOCH_LINEAR


def ym_from_months_since_epoch(alpha):
    """Z3-pure inverse: decode (year, month) from alpha months-since-epoch."""
    k = alpha + _EPOCH_LINEAR
    y = (k - IntVal(1)) / 12
    m = k - y * 12
    return y, m


# Baseline-compatible helper alias
def EOMClamp(y, m, d):
    """Z3-pure end-of-month clamping."""
    maxd = days_in_month(y, m)
    return If(d < IntVal(1), IntVal(1), If(d > maxd, maxd, d))


FOUR_HUNDRED_YEARS = IntVal(146097)  # 400*365 + 97 leap days

def add_days_ordinal(y, m, d, delta_days):
    """
    Exact ordinal-based addition via a single ordinal add.
    Steps:
      - EOM clamp input day (baseline 'round down' policy).
      - If delta_days == 0 → return (y,m,d).
      - Add delta_days in days-since-epoch space and decode.
    """

    d0 = EOMClamp(y, m, d)

    # Fast path: no day shift → avoid any ordinal math.
    no_shift = delta_days == IntVal(0)

    # Single-step ordinal addition
    z = days_since_epoch_from_ymd(y, m, d0)
    y2, m2, d2 = ymd_from_days_since_epoch(z + delta_days)

    # If delta_days == 0, return (y,m,d0); else the computed (y2,m2,d2)
    out_y = If(no_shift, y, y2)
    out_m = If(no_shift, m, m2)
    out_d = If(no_shift, d0, d2)
    return out_y, out_m, out_d


class DateVar:
    """Symbolic date variable using alpha-beta representation.

    alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
    beta  (beta_var):   extra days within that month (0-based), so DOM = 1+beta
    """

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Alpha: Z3 integer variable for months since epoch-month
        self.months_var = Int(f"{name}_months")
        # Beta: Z3 integer variable for extra days (0-based) within month
        self.beta_var = Int(f"{name}_beta")

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date using (alpha, beta)."""
        alpha_val = model.evaluate(self.months_var, model_completion=True).as_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_long()
        # Decode year/month from alpha
        k = alpha_val + (2000 * 12 + 3)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        return Date(year, month, day)

    def __ge__(self, other):
        """Support x >= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
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

    def __le__(self, other):
        """Support x <= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
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

    def __lt__(self, other):
        """Support x < date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other):
        """Support x > date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        elif isinstance(other, DateVar):
            return And(self.months_var == other.months_var, self.beta_var == other.beta_var)
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        """DateVar + Period/PeriodVar using alpha for Y/M and beta for D.
        Steps:
          - If constant days-only period, shift beta only.
          - Otherwise add months to alpha, clamp EOM using current day,
            then add days in ordinal space and re-sync alpha/beta.
        """
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                # Constant period
                result = DateVar(
                    f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
                )
                months_delta = IntVal(other.years * 12 + other.months)
                days_delta = IntVal(other.days)
            else:
                # Symbolic period
                result = DateVar(f"{self.name}_plus_{other.name}")
                months_delta = other.years * 12 + other.months
                days_delta = other.days

            # Decode current (y,m,d) from (alpha,beta)
            y0, m0 = ym_from_months_since_epoch(self.months_var)
            d0 = self.beta_var + IntVal(1)

            # Step 1: shift alpha by months
            alpha1 = self.months_var + months_delta
            y1, m1 = ym_from_months_since_epoch(alpha1)

            # Step 2: EOM clamp with current DOM
            d1 = EOMClamp(y1, m1, d0)

            # Step 3: add D days in ordinal space and resync alpha/beta
            y2, m2, d2 = add_days_ordinal(y1, m1, d1, days_delta)

            result.months_var = months_since_epoch_from_ym(y2, m2)
            result.beta_var = d2 - IntVal(1)
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __radd__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            return self.__add__(other)
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other):
        """DateVar - Period implemented as DateVar + (-Period). Date difference returns Int."""
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                neg = Period(-other.years, -other.months, -other.days)
            else:
                neg = PeriodVar(f"neg_{other.name}")
                neg.years = -other.years
                neg.months = -other.months
                neg.days = -other.days
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class PeriodVar:
    """Symbolic period variable using separate Y/M/D components (baseline-compatible)."""

    def __init__(self, name: str, years=0, months=0, days=0):
        self.name = name
        self.years = Int(f"{name}_years")
        self.months = Int(f"{name}_months")
        self.days = Int(f"{name}_days")

    def __str__(self):
        return f"PeriodVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_period(self, model: ModelRef) -> Period:
        years = model.evaluate(self.years, model_completion=True).as_long()
        months = model.evaluate(self.months, model_completion=True).as_long()
        days = model.evaluate(self.days, model_completion=True).as_long()
        return Period(years, months, days)

    def __eq__(self, other):
        raise TypeError(f"Cannot compare PeriodVar.")

    def __ne__(self, other):
        raise TypeError(f"Cannot compare PeriodVar.")

    def __add__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                result = PeriodVar(
                    f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
                )
                oy, om, od = (
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
                )
                result.years = self.years + oy
                result.months = self.months + om
                result.days = self.days + od
            else:
                result = PeriodVar(f"{self.name}_plus_{other.name}")
                result.years = self.years + other.years
                result.months = self.months + other.months
                result.days = self.days + other.days
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to PeriodVar")

    def __sub__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                result = PeriodVar(
                    f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d"
                )
                oy, om, od = (
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
                )
                result.years = self.years - oy
                result.months = self.months - om
                result.days = self.days - od
            else:
                result = PeriodVar(f"{self.name}_minus_{other.name}")
                result.years = self.years - other.years
                result.months = self.months - other.months
                result.days = self.days - other.days
            return result
        else:
            raise TypeError(f"Cannot subtract {type(other)} from PeriodVar")


class AbDateSolver:
    """Alpha-beta date constraint solver using epoch-based conversion."""

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

        # Alpha bounds: months since 2000-03
        # 1900-01 => (1900-2000)*12 + (1-3) = -1202
        # 2100-12 => (2100-2000)*12 + (12-3) = 1209
        self.solver.add(date_var.months_var >= IntVal((1900 - EPOCH_YEAR) * 12 + (1 - EPOCH_MONTH)))
        self.solver.add(date_var.months_var <= IntVal((2100 - EPOCH_YEAR) * 12 + (12 - EPOCH_MONTH)))

        # Beta bounds depend on month length: 0 <= beta < days_in_month(y,m)
        y, m = ym_from_months_since_epoch(date_var.months_var)
        self.solver.add(date_var.beta_var >= 0)
        self.solver.add(date_var.beta_var < days_in_month(y, m))

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
