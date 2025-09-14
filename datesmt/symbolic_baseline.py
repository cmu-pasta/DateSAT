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


def normalize_month_elegant(y, m, max_months=120):
    """
    Elegantly normalize (y, m) so that m in 1..12 using recursive unrolling.
    This handles months up to max_months (default 120 = 10 years).

    The function dynamically calculates the number of 12-month chunks needed
    and unrolls them into a fixed number of If statements for Z3 compatibility.
    """
    # Calculate how many 12-month chunks we need to handle
    # For max_months=120, we need to handle up to 9 chunks (120/12 = 10, so 9 adjustments)
    chunks = (max_months - 1) // 12

    # Start with the input values
    current_y, current_m = y, m

    # Unroll the normalization steps
    # Each step handles one 12-month chunk
    for i in range(chunks):
        current_y = If(current_m > 12, current_y + 1, current_y)
        current_m = If(current_m > 12, current_m - 12, current_m)

    return current_y, current_m


def next_month(y, m):
    """Get the next month, handling year rollover."""
    return normalize_month_elegant(y, m + 1)


def prev_month(y, m):
    """Get the previous month, handling year rollover."""
    y1 = If(m <= 1, y - 1, y)
    m1 = If(m <= 1, 12, m - 1)
    return y1, m1


def add_days_with_bounded_carry(y, m, d, delta_days):
    """
    Add delta_days to (y,m,d) with at most two month crossings in either direction.
    This covers |delta_days| <= 62 safely across all calendars.
    """
    dim = days_in_month(y, m)
    dsum = d + delta_days

    # Case A: stays within current month
    stay = And(dsum >= 1, dsum <= dim)

    # Case B: overflows to next month (at most one hop)
    yA, mA = next_month(y, m)
    dimA = days_in_month(yA, mA)
    dB = dsum - dim
    over1 = And(dsum > dim, dB >= 1, dB <= dimA)

    # Case B2: overflows two months ahead
    yB2, mB2 = next_month(yA, mA)
    dimB2 = days_in_month(yB2, mB2)
    dB2 = dsum - dim - dimA
    over2 = And(dsum > dim, dB > dimA, dB2 >= 1, dB2 <= dimB2)

    # Case C: underflows to previous month (at most one hop)
    yC, mC = prev_month(y, m)
    dimC = days_in_month(yC, mC)
    dC = dimC + dsum  # since dsum <= 0 here
    under1 = And(dsum < 1, dC >= 1, dC <= dimC)

    # Case C2: underflows two months back
    yC2, mC2 = prev_month(yC, mC)
    dimC2 = days_in_month(yC2, mC2)
    dC2 = dimC2 + dsum + dimC
    under2 = And(dsum < 1, dC < 1, dC2 >= 1, dC2 <= dimC2)

    out_y = If(
        stay, y, If(over1, yA, If(over2, yB2, If(under1, yC, If(under2, yC2, y))))
    )

    out_m = If(
        stay, m, If(over1, mA, If(over2, mB2, If(under1, mC, If(under2, mC2, m))))
    )

    out_d = If(
        stay,
        dsum,
        If(
            over1,
            dB,
            If(over2, dB2, If(under1, dC, If(under2, dC2, If(dsum < 1, 1, dim)))),
        ),
    )

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
        year = model[self.year_var].as_long()
        month = model[self.month_var].as_long()
        day = model[self.day_var].as_long()
        return Date(year, month, day)

    def __ge__(self, other):
        """Support x >= date comparison."""
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
        """Support x <= date comparison."""
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
        """Support x < date comparison."""
        if isinstance(other, Date):
            return Not(self.__ge__(other))
        elif isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison."""
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

    def __add__(self, other):
        """DateVar + Period using component-based arithmetic with proper day validation."""
        if isinstance(other, Period):
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
            )

            # 1) Add years & months, then normalize months into 1..12 with year carry.
            y0 = self.year_var + other.years
            m0 = self.month_var + other.months
            y1, m1 = normalize_month_elegant(y0, m0)

            # 2) Clamp the base day into valid range of (y1,m1) before adding day delta.
            maxd = days_in_month(y1, m1)
            d0 = self.day_var
            d1 = If(d0 < 1, 1, If(d0 > maxd, maxd, d0))

            # 3) Add days with bounded month carry (±2 months). Extend unroll if needed.
            y2, m2, d2 = add_days_with_bounded_carry(y1, m1, d1, other.days)

            # 4) CRITICAL: Ensure the final day is valid for the target month/year
            # This prevents invalid dates like 2021-02-29
            maxd_final = days_in_month(y2, m2)
            final_day = If(d2 < 1, 1, If(d2 > maxd_final, maxd_final, d2))

            result.year_var = y2
            result.month_var = m2
            result.day_var = final_day

            return result
        elif isinstance(other, PeriodVar):
            # For symbolic period addition, create a new DateVar
            result = DateVar(f"{self.name}_plus_period")
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __radd__(self, other):
        """Support period + date addition."""
        return self.__add__(other)

    def add_valid_date_constraints(self, solver):
        """Add constraints to ensure this DateVar represents a valid date."""
        # Basic range constraints
        # solver.add(self.year_var >= 1900)
        # solver.add(self.year_var <= 2100)
        solver.add(self.month_var >= 1)
        solver.add(self.month_var <= 12)
        solver.add(self.day_var >= 1)
        solver.add(self.day_var <= 31)

        # Month-specific day constraints
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

    def __init__(self, name: str):
        """Create a symbolic period variable."""
        self.name = name
        # Create separate Z3 integer variables for years, months, days
        self.years_var = Int(f"{name}_years")
        self.months_var = Int(f"{name}_months")
        self.days_var = Int(f"{name}_days")

    def __str__(self):
        return f"PeriodVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_period(self, model: ModelRef) -> Period:
        """Convert Z3 model to concrete Period."""
        years = model[self.years_var].as_long()
        months = model[self.months_var].as_long()
        days = model[self.days_var].as_long()
        return Period(years, months, days)


class DateSolver:
    """Baseline date constraint solver using component-based representation."""

    def __init__(self):
        """Initialize the solver."""
        self.solver = Solver()
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with comprehensive date validation."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Add comprehensive date validation constraints
        date_var.add_valid_date_constraints(self.solver)

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
