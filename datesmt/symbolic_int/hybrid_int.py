"""
Hybrid DATE-SMT implementation using dual representation.

This module implements the hybrid approach where dates are represented
using dual representation: epoch-primary, YMD-derived. Each date has:
- epoch_var: Z3 Int, days since 2000-03-01 (primary for comparisons/day ops)
- year/month/day vars: created lazily when needed; with a forward link
  epoch_var == days_since_epoch_from_ymd(year, month, day)

Comparisons and day arithmetic use O(1) epoch operations; month/year
arithmetic uses simple AMI on (Y,M,D) components without re-encoding to
epoch unless needed. Period addition matches epoch_days semantics but avoids
encoding back to epoch when not necessary.
"""

from datetime import date, timedelta
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

from ..core import Date, Period


def from_days_since_epoch(days: int) -> Date:
    """Convert days since epoch to a Date using a more robust approach."""
    # March 1, 2000 is day 0
    # Convert our epoch to Python date
    epoch_python = date(2000, 3, 1)

    # Add the days
    result_python = epoch_python + timedelta(days=days)

    # Convert back to our Date class
    return Date(result_python.year, result_python.month, result_python.day)


def to_days_since_epoch(date_obj: Date) -> int:
    """Convert a Date to days since epoch (March 1, 2000) using a more robust approach."""
    # March 1, 2000 is day 0
    # Convert to Python dates
    epoch_python = date(2000, 3, 1)
    target_python = date(date_obj.year, date_obj.month, date_obj.day)

    # Calculate the difference
    delta = target_python - epoch_python
    return delta.days


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


def normalize_month(y, m):
    """Z3-pure month normalization (1..12)."""
    t = m - IntVal(1)
    q = t / IntVal(12)  # Z3 integer division
    r = t % IntVal(12)  # Z3 modulo
    return y + q, r + IntVal(1)


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
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str):
        self.ctx = ctx
        self.name = name
        # Primary epoch representation
        self.epoch_var = Int(f"{name}_epoch")
        # Lazy YMD vars
        self._ymd_exists = False
        self._year_var = None
        self._month_var = None
        self._day_var = None
        self._forward_link_added = False
        # Tracks whether epoch_var and (Y,M,D) are linked for this var
        self._epoch_ymd_consistent = False

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    # Back-compat property name used in some places
    @property
    def days_var(self):
        return self.epoch_var

    @property
    def year_var(self):
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._year_var

    @property
    def month_var(self):
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._month_var

    @property
    def day_var(self):
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._day_var

    def _ensure_ymd(self):
        if self._ymd_exists:
            return
        self._year_var = Int(f"{self.name}_year")
        self._month_var = Int(f"{self.name}_month")
        self._day_var = Int(f"{self.name}_day")
        self._ymd_exists = True
        # Add validity constraints
        self.ctx._add_date_constraints(self)
        # Add forward link
        self._add_forward_link()

    def _add_forward_link(self):
        if self._forward_link_added:
            return
        self.ctx.solver.add(
            self.epoch_var
            == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)
        )
        self._forward_link_added = True
        self._epoch_ymd_consistent = True

    def to_concrete_date(self, model: ModelRef) -> Date:
        if self._ymd_exists:
            y = model.evaluate(self._year_var, model_completion=True).as_long()
            m = model.evaluate(self._month_var, model_completion=True).as_long()
            d = model.evaluate(self._day_var, model_completion=True).as_long()
            return Date(y, m, d)
        else:
            e = model.evaluate(self.epoch_var, model_completion=True).as_long()
            return from_days_since_epoch(e)

    def __ge__(self, other):
        """Support x >= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to epoch days if needed
            if isinstance(other, Date):
                other_epoch = to_days_since_epoch(other)
            else:  # isinstance(other, DateVar)
                other_epoch = other.epoch_var

            return self.epoch_var >= other_epoch
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        """Support x <= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to epoch days if needed
            if isinstance(other, Date):
                other_epoch = to_days_since_epoch(other)
            else:  # isinstance(other, DateVar)
                other_epoch = other.epoch_var

            return self.epoch_var <= other_epoch
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
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to epoch days if needed
            if isinstance(other, Date):
                other_epoch = to_days_since_epoch(other)
            else:  # isinstance(other, DateVar)
                other_epoch = other.epoch_var

            return self.epoch_var == other_epoch
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        """Hybrid date + Period: mirror epoch_days semantics, but avoid epoch encode unless days-only.

        - days-only: epoch add (O(1))
        - months/years (and mixed): decode epoch→YMD, normalize months, clamp, add days via ordinal,
          then set result's Y/M/D; epoch derives later when needed.
        """
        if not (isinstance(other, Period) or isinstance(other, PeriodVar)):
            raise TypeError(f"Cannot add {type(other)} to DateVar")

        result = self.ctx.add_date_var(f"{self.name}_plus")

        # Concrete Period fast-path for days-only
        if isinstance(other, Period) and other.years == 0 and other.months == 0:
            self.ctx.solver.add(result.epoch_var == self.epoch_var + IntVal(other.days))
            return result

        # Extract period components as Z3 terms
        if isinstance(other, Period):
            oy, om, od = IntVal(other.years), IntVal(other.months), IntVal(other.days)
        else:
            oy, om, od = other.years, other.months, other.days

        # Decode current epoch to Y/M/D (pure Z3 terms), unless we already have
        # materialized, consistent Y/M/D variables for this date
        if self._ymd_exists and self._epoch_ymd_consistent:
            y0, m0, d0 = self._year_var, self._month_var, self._day_var
        else:
            y0, m0, d0 = ymd_from_days_since_epoch(self.epoch_var)
        # Step 1: combine years/months with AMI normalization
        period_total_months = oy * IntVal(12) + om
        total_months = m0 + period_total_months
        year_carry, m1 = normalize_month(IntVal(0), total_months)
        y1 = y0 + year_carry
        # Step 2: EOM clamp
        d1 = EOMClamp(y1, m1, d0)
        # Step 3: add days in ordinal space
        y2, m2, d2 = add_days_ordinal(y1, m1, d1, od)
        # Constrain result Y/M/D only (epoch will be derived on demand)
        self.ctx.solver.add(result.year_var == y2)
        self.ctx.solver.add(result.month_var == m2)
        self.ctx.solver.add(result.day_var == d2)
        return result

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


class HybridSolver:
    """Hybrid date constraint solver using dual representation (epoch + YMD)."""

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
        if name is None:
            name = f"d{len(self.date_vars)}"
        # Ensure uniqueness to avoid collisions when creating multiple temporaries
        base_name = name
        suffix = 0
        while name in self.date_vars:
            suffix += 1
            name = f"{base_name}_{suffix}"
        dv = DateVar(self, name)
        self.date_vars[name] = dv

        # Basic epoch range constraints [1900-03-01 .. 2100-02-28]
        self.solver.add(dv.epoch_var >= -36525)
        self.solver.add(dv.epoch_var <= 36523)
        return dv

    def _add_date_constraints(self, dv: DateVar):
        if not dv._ymd_exists:
            return
        Y, M, D = dv._year_var, dv._month_var, dv._day_var
        # Year bounds consistent with epoch bounds
        Y_MIN, Y_MAX = 1900, 2100
        self.solver.add(
            And(
                Y >= Y_MIN,
                Y <= Y_MAX,
                M >= 1,
                M <= 12,
                D >= 1,
                D <= days_in_month(Y, M),
            )
        )

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
