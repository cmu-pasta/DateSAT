"""
Core Date and Period classes for DateSAT.

These classes represent the basic data structures used by all approaches.
The difference between approaches is in how these are converted to Z3 constraints,
not in the data representation itself.
"""

import warnings
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from z3 import *

from .bounds import DEFAULT_BOUND_MODE, get_bound_spec

# Process-wide bound mode for CONCRETE Date/Period semantics (the symbolic
# side is configured per-solver via the `bound` parameter). In "paper" mode,
# constructing a Date outside [1900-03-01 .. 2100-02-28] raises
# "Date outside allowed range" — which datesat.solver converts to UNSAT for
# intermediate results — and Period components are range-checked, matching the
# original bounded evaluation. In "datetime"/"none" modes only calendar
# correctness is validated.
_BOUND_MODE = DEFAULT_BOUND_MODE


def set_bound_mode(mode: str) -> None:
    """Set the concrete-side bound mode ('paper', 'datetime', or 'none')."""
    global _BOUND_MODE
    get_bound_spec(mode)  # validate the name
    _BOUND_MODE = mode


def get_bound_mode() -> str:
    """Return the current concrete-side bound mode."""
    return _BOUND_MODE


def _is_leap_int(year: int) -> bool:
    """Proleptic Gregorian leap-year rule as pure integer arithmetic."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_month_int(year: int, month: int) -> int:
    """Days in a month under the proleptic Gregorian calendar (pure ints)."""
    if month == 2:
        return 29 if _is_leap_int(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


class Date:
    """Date class with year/month/day representation."""

    def __init__(self, year: int, month: int, day: int, bounded: bool = None):
        """Initialize a Date with year, month, day components.

        Args:
            year: Year component
            month: Month component
            day: Day component
            bounded: Range-enforcement override. None (default) follows the
                     process-wide bound mode (see set_bound_mode): the "paper"
                     mode enforces [1900-03-01 .. 2100-02-28], other modes only
                     validate calendar correctness. False explicitly opts out
                     of range enforcement (used for model reconstruction).
        """
        self._year = year
        self._month = month
        self._day = day
        self._bounded = bounded
        self._validate()

    @property
    def year(self) -> int:
        """Get the year component."""
        return self._year

    @property
    def month(self) -> int:
        """Get the month component."""
        return self._month

    @property
    def day(self) -> int:
        """Get the day component."""
        return self._day

    def _validate(self) -> None:
        """Validate that the date components are valid."""
        # Validate input format first: all components must be integers (no bools allowed)
        date_components = (self._year, self._month, self._day)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in date_components):
            raise ValueError(
                "Invalid date format: year, month, and day must be integers"
            )

        # First, validate calendar correctness. datetime.date covers years
        # 1..9999; outside that range (possible in bound mode 'none') fall
        # back to a pure-integer proleptic Gregorian check so unbounded
        # models can still be represented.
        if 1 <= self._year <= 9999:
            try:
                date(self._year, self._month, self._day)
            except ValueError as e:
                raise ValueError(
                    f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
                ) from e
        else:
            if not (
                1 <= self._month <= 12
                and 1 <= self._day <= _days_in_month_int(self._year, self._month)
            ):
                raise ValueError(
                    f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
                )

        # Range enforcement depends on the process-wide bound mode. Only the
        # "paper" mode enforces a window; "datetime" is already guaranteed by
        # the calendar check above (datetime.date covers years 1..9999) and
        # "none" adds nothing. bounded=False explicitly opts out (used when
        # reconstructing models that legitimately exceeded the concrete range).
        if _BOUND_MODE == "paper" and self._bounded is not False:
            spec = get_bound_spec("paper")
            if date_components < spec.min_ymd or date_components > spec.max_ymd:
                raise ValueError(
                    f"Date outside allowed range: {self._year}-{self._month:02d}-{self._day:02d} (allowed [1900-03-01..2100-02-28])"
                )

    def __str__(self) -> str:
        """Return a string representation of the Date."""
        return f"Date({self.year}, {self.month}, {self.day})"

    def __hash__(self) -> int:
        """Return hash value for Date object."""
        return hash((self.year, self.month, self.day))

    def __eq__(self, other: "Date") -> bool:
        """Check if two dates are equal."""
        if isinstance(other, Date):
            return (
                self.year == other.year
                and self.month == other.month
                and self.day == other.day
            )
        # Allow DateVar implementations to handle reflected comparison
        # Includes: symbolic DateVar, EvalDateVar (validation), EnumerationDateVar (baseline)
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __ne__(self, other: "Date") -> bool:
        """Check if two dates are not equal."""
        if isinstance(other, Date):
            return not self.__eq__(other)
        # Allow DateVar implementations to handle reflected comparison
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")
    
    def __lt__(self, other: "Date"):
        """Check if this date is less than another."""
        if isinstance(other, Date):
            return self.to_python_date() < other.to_python_date()
        # Allow DateVar implementations to handle reflected comparison
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")
    
    def __le__(self, other: "Date"):
        """Check if this date is less than or equal to another."""
        if isinstance(other, Date):
            return self.to_python_date() <= other.to_python_date()
        # Allow DateVar implementations to handle reflected comparison
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")
    
    def __gt__(self, other: "Date"):
        """Check if this date is greater than another."""
        if isinstance(other, Date):
            return self.to_python_date() > other.to_python_date()
        # Allow DateVar implementations to handle reflected comparison
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")
    
    def __ge__(self, other: "Date"):
        """Check if this date is greater than or equal to another."""
        if isinstance(other, Date):
            return self.to_python_date() >= other.to_python_date()
        # Allow DateVar implementations to handle reflected comparison
        other_cls = other.__class__
        other_name = other_cls.__name__
        if (other_name in ("DateVar", "EvalDateVar", "EnumerationDateVar") or
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic"))):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def to_python_date(self) -> date:
        """Convert to Python date object."""
        return date(self.year, self.month, self.day)

    @classmethod
    def from_python_date(cls, d: date) -> "Date":
        """Create Date from Python date object."""
        return cls(d.year, d.month, d.day)

    def __add__(self, other: "Period"):
        """
        Date + Period using Python's datetime library with relativedelta.
        This provides the same semantics as the symbolic DateVar operations.
        Date is no longer range-bounded, so any calendar-valid result is returned.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to Date")

        py_date = self.to_python_date()
        result_date = py_date + relativedelta(
            years=other.years, months=other.months, days=other.days
        )
        return Date.from_python_date(result_date)

    def __sub__(self, other: "Period"):
        """
        Date - Period implemented as Date + (-Period).
        Date is no longer range-bounded, so any calendar-valid result is returned.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot subtract {type(other)} from Date")

        neg_period = Period(-other.years, -other.months, -other.days)
        return self.__add__(neg_period)


class Period:
    """Period class for representing time periods."""

    # Period bounds based on date range [1900-03-01 to 2100-02-28]
    # These match the allowed date range to ensure periods are semantically valid
    MAX_PERIOD_DAYS = 73048  # abs(EPOCH_DAYS_MAX - EPOCH_DAYS_MIN) = abs(36523 - (-36525))
    MAX_PERIOD_YEARS = 200  # YEAR_MAX - YEAR_MIN = 2100 - 1900
    MAX_PERIOD_MONTHS = 2400  # MAX_PERIOD_YEARS * 12 = 200 * 12

    def __init__(self, years: int, months: int, days: int):
        """Initialize a Period with years, months, days components."""
        # Validate input format: exactly three integer components (no bools allowed)
        period_components = (years, months, days)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in period_components):
            raise ValueError(
                "Invalid Period format: years, months, and days must be integers"
            )

        # Period range checks apply only in "paper" bound mode, where periods
        # must fit within the bounded date window (original evaluation
        # semantics). Other modes allow any integer period.
        if _BOUND_MODE == "paper":
            if abs(years) > self.MAX_PERIOD_YEARS:
                raise ValueError(
                    f"Period years out of range: {years} (max ±{self.MAX_PERIOD_YEARS})"
                )
            if abs(months) > self.MAX_PERIOD_MONTHS:
                raise ValueError(
                    f"Period months out of range: {months} (max ±{self.MAX_PERIOD_MONTHS})"
                )
            if abs(days) > self.MAX_PERIOD_DAYS:
                raise ValueError(
                    f"Period days out of range: {days} (max ±{self.MAX_PERIOD_DAYS})"
                )

        self._years = years
        self._months = months
        self._days = days

    @property
    def years(self) -> int:
        """Get the years component."""
        return self._years

    @property
    def months(self) -> int:
        """Get the months component."""
        return self._months

    @property
    def days(self) -> int:
        """Get the days component."""
        return self._days

    def __str__(self) -> str:
        return f"Period({self.years}, {self.months}, {self.days})"

    def __hash__(self) -> int:
        """Return hash value for Period object."""
        return hash((self.years, self.months, self.days))

    def __eq__(self, other: "Period") -> bool:
        raise TypeError(f"Cannot compare Period with {type(other)}")

    def __ne__(self, other: "Period") -> bool:
        raise TypeError(f"Cannot compare Period with {type(other)}")

    def __mul__(self, other: int) -> "Period":
        """Support Period * Int multiplication."""
        if isinstance(other, int):
            return Period(
                self.years * other,
                self.months * other,
                self.days * other
            )
        else:
            raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __rmul__(self, other: int) -> "Period":
        """Support Int * Period multiplication."""
        if isinstance(other, int):
            return self.__mul__(other)
        else:
            raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __add__(self, other: "Period") -> "Period":
        """Support Period + Period addition."""
        if isinstance(other, Period):
            return Period(
                self.years + other.years,
                self.months + other.months,
                self.days + other.days
            )
        else:
            # Delegate to the right operand's __radd__ method
            return NotImplemented

    def __sub__(self, other: "Period") -> "Period":
        """Support Period - Period subtraction."""
        if isinstance(other, Period):
            return Period(
                self.years - other.years,
                self.months - other.months,
                self.days - other.days
            )
        else:
            return NotImplemented
