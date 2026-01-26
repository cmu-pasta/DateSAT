"""
Core Date and Period classes for DATE-SMT.

These classes represent the basic data structures used by all approaches.
The difference between approaches is in how these are converted to Z3 constraints,
not in the data representation itself.
"""

import warnings
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from z3 import *


class Date:
    """Date class with year/month/day representation."""

    def __init__(self, year: int, month: int, day: int, bounded: bool = True):
        """Initialize a Date with year, month, day components.
        
        Args:
            year: Year component
            month: Month component
            day: Day component
            bounded: If True (default), validates that the date is within the allowed
                    range [1900-03-01 to 2100-02-28]. If False, only validates
                    calendar correctness but not range.
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

        # First, validate calendar correctness
        try:
            date(self._year, self._month, self._day)
        except ValueError as e:
            raise ValueError(
                f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
            ) from e

        # Next, enforce allowed window [1900-03-01 - 2100-02-28] only if bounded
        if self._bounded:
            min_allowed = (1900, 3, 1)
            max_allowed = (2100, 2, 28)

            if date_components < min_allowed or date_components > max_allowed:
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
            (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesmt.symbolic"))):
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
        
        Intermediate dates must be within the allowed range [1900-03-01, 2100-02-28].
        If the result is outside this range, raises ValueError to ensure consistency
        with symbolic DateVar bounds enforcement (which makes constraints UNSAT).
        This error should be caught during constraint building and converted to an UNSAT constraint.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to Date")
        
        # Convert to Python date and use relativedelta for years/months/days
        py_date = self.to_python_date()
        result_date = py_date + relativedelta(
            years=other.years, months=other.months, days=other.days
        )
        
        # Try to convert back to Date (will validate the result and enforce bounds)
        # This ensures intermediate dates are bounded, consistent with symbolic DateVars
        # If out of bounds, ValueError is raised and should be caught during constraint building
        # to convert to an UNSAT constraint
        return Date.from_python_date(result_date)

    def __sub__(self, other: "Period"):
        """
        Date - Period implemented as Date + (-Period).
        
        Intermediate dates must be within the allowed range [1900-03-01, 2100-02-28].
        If the result is outside this range, raises ValueError to ensure consistency
        with symbolic DateVar bounds enforcement (which makes constraints UNSAT).
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

        # Validate period bounds: ensure periods fit within the allowed date range
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
