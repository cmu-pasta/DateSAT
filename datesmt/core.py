"""
Core Date and Period classes for DATE-SMT.

These classes represent the basic data structures used by both baseline
and epoch_days approaches. The difference between approaches is in how
these are converted to Z3 constraints, not in the data representation.
"""

from datetime import date, timedelta

from z3 import *


class Date:
    """Date class with year/month/day representation."""

    def __init__(self, year: int, month: int, day: int):
        """Initialize a Date with year, month, day components."""
        self._year = year
        self._month = month
        self._day = day
        self._validate()

    @property
    def year(self):
        """Get the year component."""
        return self._year

    @property
    def month(self):
        """Get the month component."""
        return self._month

    @property
    def day(self):
        """Get the day component."""
        return self._day

    def _validate(self):
        """Validate that the date components are valid."""
        # Validate input format first: all components must be integers (bools are not allowed)
        components = (self._year, self._month, self._day)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in components):
            raise ValueError(
                "Invalid date format: year, month, and day must be integers"
            )

        # First, validate calendar correctness. If components are invalid
        # (e.g., month out of [1..12], day out of range, unsupported year),
        # raise an Invalid date error regardless of range.
        try:
            date(self._year, self._month, self._day)
        except ValueError as e:
            raise ValueError(
                f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
            ) from e

        # Next, enforce inclusive allowed window [1900-03-01 .. 2100-02-28]
        min_allowed = (1900, 3, 1)
        max_allowed = (2100, 2, 28)
        current = (self._year, self._month, self._day)

        if current < min_allowed or current > max_allowed:
            raise ValueError(
                f"Date outside allowed range: {self._year}-{self._month:02d}-{self._day:02d} (allowed [1900-03-01..2100-02-28])"
            )

    def __str__(self):
        return f"Date({self.year}, {self.month}, {self.day})"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        """Return hash value for Date object."""
        return hash((self.year, self.month, self.day))

    def __eq__(self, other):
        """Check if two dates are equal."""
        if not isinstance(other, Date):
            return False
        return (
            self.year == other.year
            and self.month == other.month
            and self.day == other.day
        )

    def to_python_date(self) -> date:
        """Convert to Python date object."""
        return date(self.year, self.month, self.day)

    @classmethod
    def from_python_date(cls, d: date):
        """Create Date from Python date object."""
        return cls(d.year, d.month, d.day)


class Period:
    """Period class for representing time periods."""

    def __init__(self, years: int, months: int, days: int):
        """Initialize a Period with years, months, days components."""
        # Validate input format: exactly three integer components (reject bools)
        components = (years, months, days)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in components):
            raise ValueError(
                "Invalid Period format: years, months, and days must be integers"
            )

        self._years = years
        self._months = months
        self._days = days

    @property
    def years(self):
        """Get the years component."""
        return self._years

    @property
    def months(self):
        """Get the months component."""
        return self._months

    @property
    def days(self):
        """Get the days component."""
        return self._days

    def __str__(self):
        return f"Period({self.years}, {self.months}, {self.days})"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        """Return hash value for Period object."""
        return hash((self.years, self.months, self.days))

    def __eq__(self, other):
        """Check if two periods are equal."""
        if not isinstance(other, Period):
            return False
        return (
            self.years == other.years
            and self.months == other.months
            and self.days == other.days
        )

    def __mul__(self, other):
        """Support Period * Int multiplication."""
        if isinstance(other, int):
            return Period(
                self.years * other,
                self.months * other,
                self.days * other
            )
        else:
            raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __rmul__(self, other):
        """Support Int * Period multiplication."""
        if isinstance(other, int):
            return self.__mul__(other)
        else:
            raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __add__(self, other):
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

    def __sub__(self, other):
        """Support Period - Period subtraction."""
        if isinstance(other, Period):
            return Period(
                self.years - other.years,
                self.months - other.months,
                self.days - other.days
            )
        else:
            return NotImplemented
