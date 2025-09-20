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

    def __add__(self, other):
        """Support date + period addition.

        Accepts a concrete Period or a PeriodVar (approximate days) and returns a new DateVar.
        """
        if isinstance(other, Period):
            result_days = self.days_var + to_days_approximate(other)
            result = DateVar(
                f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
            )
            result.days_var = result_days
            return result
        from .symbolic_advanced import (
            PeriodVar as _PeriodVar,  # local import to avoid circular typing
        )

        if isinstance(other, _PeriodVar):
            result = DateVar(f"{self.name}_plus_{other.name}")
            result.days_var = self.days_var + other.days_var
            return result
        raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __radd__(self, other):
        """Support period + date addition."""
        return self.__add__(other)


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


class AdvancedDateSolver:
    """Advanced date constraint solver using epoch-based conversion."""

    def __init__(self):
        """Initialize the solver."""
        self.solver = Solver()
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Add basic constraints for valid date ranges
        # Roughly map civil years 1900..2100 into day offsets to prevent negative years
        # Use a wide band to avoid over-constraining while blocking absurd negatives
        self.solver.add(
            date_var.days_var >= -36525
        )  # allow dating back ~100 years before epoch
        self.solver.add(date_var.days_var <= 36525)  # and ~100 years after

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
