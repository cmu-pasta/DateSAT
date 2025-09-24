"""
Baseline DATE-SMT implementation using component-based representation.

This module implements the baseline approach where dates are represented
as separate year, month, and day variables, and period arithmetic is done
component-wise with proper normalization.
"""

from typing import Union

from z3 import (
    And,
    BoolRef,
    CheckSatResult,
    If,
    Int,
    ModelRef,
    Not,
    Or,
    Solver,
    sat,
    unsat,
    is_expr,
    IntVal,
)

from .core import Date, Period


def is_leap(year):
    """Check if a year is a leap year."""
    return Or(And(year % 4 == 0, year % 100 != 0), year % 400 == 0)


def days_in_month(year, month):
    """Get the number of days in a month, accounting for leap years."""
    return If(
        month == 2,
        If(is_leap(year), 29, 28),
        If(Or(month == 4, month == 6, month == 9, month == 11), 30, 31),
    )


def normalize_month(y, m):
    """
    NormMonth(y,m) = (y + ((m-1) div 12), ((m-1) mod 12) + 1)
    Works for concrete and symbolic inputs.
    """
    t = m - IntVal(1)
    q = t / IntVal(12)       # Z3 integer division
    r = t % IntVal(12)       # Z3 modulo
    return y + q, r + IntVal(1)


def canon_months(years, months):
    """
    CanonMonths(Y,M) = (Y + (M div 12), M mod 12).
    Months canonicalized to 0..11.
    """
    q = months / IntVal(12)
    r = months % IntVal(12)
    return years + q, r



def days_before_year(y):
    """
    Days from 0001-01-01 to Jan 1 of year y (0-based), Gregorian rules.
    """
    y1 = y - IntVal(1)
    return (
        IntVal(365) * y1
        + y1 / IntVal(4)
        - y1 / IntVal(100)
        + y1 / IntVal(400)
    )

_NONLEAP_PREFIX = [0,31,59,90,120,151,181,212,243,273,304,334]
_LEAP_PREFIX    = [0,31,60,91,121,152,182,213,244,274,305,335]

def _dbm_index(y, idx):
    """days_before_month for fixed idx∈{1..12} as a Z3 term."""
    non = IntVal(_NONLEAP_PREFIX[idx-1])
    lep = IntVal(_LEAP_PREFIX[idx-1])
    return If(is_leap(y), lep, non)

def days_before_month(y, m):
    """Z3 piecewise selection (no Python control over symbolic m)."""
    expr = IntVal(0)
    for i in range(1, 13):
        expr = If(m == IntVal(i), _dbm_index(y, i), expr)
    return expr
    

def _days_from_civil(y, m, d):
    """Convert year/month/day to ordinal days using the efficient algorithm from advanced implementation."""
    return days_before_year(y) + days_before_month(y, m) + (d - IntVal(1))

def _civil_from_days(z):
    """Convert ordinal days to year/month/day using 400/100/4/1 year block decomposition."""
    # 400/100/4/1 year block decomposition
    D400, D100, D4, D1 = IntVal(146097), IntVal(36524), IntVal(1461), IntVal(365)
    q400, r400 = z / D400, z % D400

    q100_raw = r400 / D100
    q100     = If(q100_raw >= IntVal(4), IntVal(3), q100_raw)    # clamp 0..3
    r100     = r400 - q100 * D100

    q4, r4   = r100 / D4, r100 % D4

    q1_raw = r4 / D1
    q1     = If(q1_raw >= IntVal(4), IntVal(3), q1_raw)          # clamp 0..3
    r1     = r4 - q1 * D1                                        # day-of-year (0..365)

    year = q400 * IntVal(400) + q100 * IntVal(100) + q4 * IntVal(4) + q1 + IntVal(1)

    # month = max i with r1 >= DBM(year, i)
    dbm = [_dbm_index(year, i) for i in range(1, 13)]
    month = IntVal(1)
    for i in range(2, 13):
        month = If(r1 >= dbm[i-1], IntVal(i), month)

    # day = r1 - DBM(year, month) + 1
    day_expr = r1 - dbm[0] + IntVal(1)
    for i in range(2, 13):
        day_expr = If(r1 >= dbm[i-1], r1 - dbm[i-1] + IntVal(1), day_expr)

    return year, month, day_expr


def EOMClamp(year, month, day):
    """
    End-of-month clamp: ensure day is valid for the given year/month.
    """
    max_day = days_in_month(year, month)
    return If(day < 1, 1, If(day > max_day, max_day, day))


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
    d0 = EOMClamp(y, m, d)

    # Fast path: no day shift → avoid any ordinal math.
    no_shift = (delta_days == IntVal(0))
    y_ns, m_ns, d_ns = y, m, d0

    # Reduce by 400-year eras to keep terms small
    q = delta_days / FOUR_HUNDRED_YEARS
    r = delta_days % FOUR_HUNDRED_YEARS

    # Shift whole eras in the year; month/day unchanged for this step
    y_era = y + q * IntVal(400)

    # Now add the small remainder r via ordinal conversion
    z   = _days_from_civil(y_era, m, d0)
    z2  = z + r
    y2, m2, d2 = _civil_from_days(z2)

    # If delta_days == 0, return (y,m,d0); else the computed (y2,m2,d2)
    out_y = If(no_shift, y_ns, y2)
    out_m = If(no_shift, m_ns, m2)
    out_d = If(no_shift, d_ns, d2)
    return out_y, out_m, out_d


class DateVar:
    """Symbolic date variable for baseline implementation."""

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Create separate Z3 integer variables for year, month, day
        self.year_var = Int(f"{name}_year")
        self.month_var = Int(f"{name}_month")
        self.day_var = Int(f"{name}_day")

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date."""
        year = model.evaluate(self.year_var, model_completion=True).as_long()
        month = model.evaluate(self.month_var, model_completion=True).as_long()
        day = model.evaluate(self.day_var, model_completion=True).as_long()
        return Date(year, month, day)

    def __ge__(self, other):
        """Support x >= date comparison using lexicographic ordering."""
        if isinstance(other, Date):
            return Or(
                self.year_var > other.year,
                And(
                    self.year_var == other.year,
                    Or(
                        self.month_var > other.month,
                        And(self.month_var == other.month, self.day_var >= other.day),
                    ),
                ),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.year_var > other.year_var,
                And(
                    self.year_var == other.year_var,
                    Or(
                        self.month_var > other.month_var,
                        And(
                            self.month_var == other.month_var,
                            self.day_var >= other.day_var,
                        ),
                    ),
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        """Support x <= date comparison using lexicographic ordering."""
        if isinstance(other, Date):
            return Or(
                self.year_var < other.year,
                And(
                    self.year_var == other.year,
                    Or(
                        self.month_var < other.month,
                        And(self.month_var == other.month, self.day_var <= other.day),
                    ),
                ),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.year_var < other.year_var,
                And(
                    self.year_var == other.year_var,
                    Or(
                        self.month_var < other.month_var,
                        And(
                            self.month_var == other.month_var,
                            self.day_var <= other.day_var,
                        ),
                    ),
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other):
        """Support x < date comparison using lexicographic ordering."""
        if isinstance(other, Date):
            return Not(self.__ge__(other))
        elif isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison using lexicographic ordering."""
        if isinstance(other, Date):
            return And(
                self.year_var == other.year,
                self.month_var == other.month,
                self.day_var == other.day,
            )
        elif isinstance(other, DateVar):
            return And(
                self.year_var == other.year_var,
                self.month_var == other.month_var,
                self.day_var == other.day_var,
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other):
        """Support x > date comparison using lexicographic ordering."""
        if isinstance(other, Date):
            return Not(self.__le__(other))
        elif isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison using ordinal arithmetic."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        """DateVar + Period using baseline: NormMonth → EOM round-down → ordinal day add."""
        if isinstance(other, Period):
            result = DateVar(f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d")

            # 1) years+months, then normalize month into 1..12 with year carry
            y0 = self.year_var + other.years
            m0 = self.month_var + other.months
            y1, m1 = normalize_month(y0, m0)

            # 2) EOM policy: clamp day into valid range of (y1, m1)
            d1 = EOMClamp(y1, m1, self.day_var)

            # 3) NormDay by exact ordinal add of D days
            y2, m2, d2 = add_days_ordinal(y1, m1, d1, other.days)

            result.year_var, result.month_var, result.day_var = y2, m2, d2
            return result

        elif isinstance(other, PeriodVar):
            result = DateVar(f"{self.name}_plus_{other.name}")

            # 1) years+months, normalize
            y0 = self.year_var + other.years_var
            m0 = self.month_var + other.months_var
            y1, m1 = normalize_month(y0, m0)

            # 2) EOM clamp
            d1 = EOMClamp(y1, m1, self.day_var)

            # 3) ordinal add with symbolic days
            y2, m2, d2 = add_days_ordinal(y1, m1, d1, other.days_var)

            result.year_var, result.month_var, result.day_var = y2, m2, d2
            return result

        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")



    def __radd__(self, other):
        """Support period + date addition."""
        return self.__add__(other)

    def __sub__(self, other):
        """DateVar - Period implemented as DateVar + (-Period)."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)

        elif isinstance(other, PeriodVar):
            from datesmt.core import PeriodVar  # adjust import if needed
            neg = PeriodVar(
                years_var = -other.years_var,
                months_var = -other.months_var,
                days_var = -other.days_var,
                name = f"neg_{other.name}",
            )
            return self.__add__(neg)

        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")

    def add_valid_date_constraints(self, solver, min_year=None, max_year=None):
        """Add constraints to ensure this DateVar represents a valid date."""
        # Basic range constraints
        if min_year is not None:
            solver.add(self.year_var >= min_year)
        if max_year is not None:
            solver.add(self.year_var <= max_year)
        solver.add(self.month_var >= 1)
        solver.add(self.month_var <= 12)
        solver.add(self.day_var >= 1)
        solver.add(self.day_var <= 31)

        # Month-specific day constraints using EOMClamp logic
        # February
        solver.add(
            If(
                self.month_var == 2,
                If(is_leap(self.year_var), self.day_var <= 29, self.day_var <= 28),
                True,
            )
        )

        # 30-day months (April, June, September, November)
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

        # 31-day months (January, March, May, July, August, October, December)
        # No additional constraint needed as day_var <= 31 already covers this


class PeriodVar:
    """Symbolic period variable for baseline implementation."""

    def __init__(self, name: str, years=0, months=0, days=0):
        """Create a symbolic period variable with optional initial values."""
        self.name = name
        # Create separate Z3 integer variables for years, months, days
        self.years_var = Int(f"{name}_years")
        self.months_var = Int(f"{name}_months")
        self.days_var = Int(f"{name}_days")
        
        # If initial values provided, canonicalize months
        if years != 0 or months != 0 or days != 0:
            canon_years, canon_months = canon_months(years, months)
            self.years_var = canon_years
            self.months_var = canon_months
            self.days_var = days

    def __str__(self):
        return f"PeriodVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_period(self, model: ModelRef) -> Period:
        """Convert Z3 model to concrete Period."""
        years = model.evaluate(self.years_var, model_completion=True).as_long()
        months = model.evaluate(self.months_var, model_completion=True).as_long()
        days = model.evaluate(self.days_var, model_completion=True).as_long()
        return Period(years, months, days)

    def __eq__(self, other):
        """Support equality with concrete Period or another PeriodVar."""
        if isinstance(other, Period):
            return And(
                self.years_var == other.years,
                self.months_var == other.months,
                self.days_var == other.days,
            )
        elif isinstance(other, PeriodVar):
            return And(
                self.years_var == other.years_var,
                self.months_var == other.months_var,
                self.days_var == other.days_var,
            )
        else:

            raise TypeError(f"Cannot compare PeriodVar with {type(other)}")

    def __ne__(self, other):
        """Support inequality with concrete Period or another PeriodVar."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        """Support Period + Period addition."""
        if isinstance(other, Period):
            # Component-wise addition with canonicalization
            new_years = self.years_var + other.years
            new_months = self.months_var + other.months
            new_days = self.days_var + other.days
            
            # Canonicalize months
            canon_years, canon_months_result = canon_months(new_years, new_months)
            
            result = PeriodVar(f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d")
            result.years_var = canon_years
            result.months_var = canon_months_result
            result.days_var = new_days
            return result
        elif isinstance(other, PeriodVar):
            # Symbolic period addition with canonicalization
            new_years = self.years_var + other.years_var
            new_months = self.months_var + other.months_var
            new_days = self.days_var + other.days_var
            
            # Canonicalize months
            canon_years, canon_months_result = canon_months(new_years, new_months)
            
            result = PeriodVar(f"{self.name}_plus_{other.name}")
            result.years_var = canon_years
            result.months_var = canon_months_result
            result.days_var = new_days
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to PeriodVar")

    def __sub__(self, other):
        """Support Period - Period subtraction."""
        if isinstance(other, Period):
            # Component-wise subtraction with canonicalization
            new_years = self.years_var - other.years
            new_months = self.months_var - other.months
            new_days = self.days_var - other.days
            
            # Canonicalize months
            canon_years, canon_months_result = canon_months(new_years, new_months)
            
            result = PeriodVar(f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d")
            result.years_var = canon_years
            result.months_var = canon_months_result
            result.days_var = new_days
            return result
        elif isinstance(other, PeriodVar):
            # Symbolic period subtraction with canonicalization
            new_years = self.years_var - other.years_var
            new_months = self.months_var - other.months_var
            new_days = self.days_var - other.days_var
            
            # Canonicalize months
            canon_years, canon_months_result = canon_months(new_years, new_months)
            
            result = PeriodVar(f"{self.name}_minus_{other.name}")
            result.years_var = canon_years
            result.months_var = canon_months_result
            result.days_var = new_days
            return result
        else:
            raise TypeError(f"Cannot subtract {type(other)} from PeriodVar")

    def __mul__(self, other):
        """Support Period × Int multiplication."""
        if isinstance(other, int):
            # Component-wise multiplication with canonicalization
            new_years = self.years_var * other
            new_months = self.months_var * other
            new_days = self.days_var * other
            
            # Canonicalize months
            canon_years, canon_months_result = canon_months(new_years, new_months)
            
            result = PeriodVar(f"{self.name}_times_{other}")
            result.years_var = canon_years
            result.months_var = canon_months_result
            result.days_var = new_days
            return result
        else:
            raise TypeError(f"Cannot multiply PeriodVar with {type(other)}")

    def __rmul__(self, other):
        """Support Int × Period multiplication."""
        return self.__mul__(other)


class DateSolver:
    """Baseline date constraint solver using component-based representation."""

    def __init__(self, min_year=None, max_year=None):
        """Initialize the solver with optional year bounds."""
        self.solver = Solver()
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []
        self.min_year = min_year
        self.max_year = max_year

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with comprehensive date validation."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Add comprehensive date validation constraints with configurable year bounds
        date_var.add_valid_date_constraints(self.solver, self.min_year, self.max_year)

        return date_var

    def add_period_var(self, name: str) -> PeriodVar:
        """Add a symbolic period variable."""
        period_var = PeriodVar(name)
        self.period_vars[name] = period_var
        # No hard bounds - let Z3 handle arbitrary periods
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
