"""
Core Date and Period classes for DateSAT.

These classes represent the basic data structures used by all approaches.
The difference between approaches is in how these are converted to Z3 constraints,
not in the data representation itself.
"""

from datetime import date
from typing import Tuple

from dateutil.relativedelta import relativedelta
from z3 import *


def is_leap_year(year: int) -> bool:
    """Proleptic Gregorian leap-year rule, valid for every integer year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def concrete_days_in_month(year: int, month: int) -> int:
    """Days in a month of the proleptic Gregorian calendar (month in 1..12)."""
    if month == 2:
        return 29 if is_leap_year(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def days_from_civil(year: int, month: int, day: int) -> int:
    """Days since 1970-01-01 of a proleptic Gregorian date (Hinnant's algorithm).

    Works for every integer year; Python's floor division matches the
    algorithm's handling of negative years.
    """
    y = year - (1 if month <= 2 else 0)
    era = y // 400
    yoe = y - era * 400
    mp = month - 3 if month > 2 else month + 9
    doy = (153 * mp + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(days: int) -> Tuple[int, int, int]:
    """Inverse of days_from_civil: (year, month, day) for days since 1970-01-01."""
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + (1 if m <= 2 else 0), m, d)


# Python's datetime.date covers exactly years 1..9999.
PYTHON_YEAR_MIN = 1
PYTHON_YEAR_MAX = 9999


class Date:
    """Date class with year/month/day representation.

    Two implementations live behind one class, selected by ``bounded``:

    * ``bounded=False`` (default): any calendar-valid day of the proleptic
      Gregorian calendar; the year may be zero, negative, or beyond 9999.
      Validation, comparison and Period arithmetic are integer-only.
    * ``bounded=True``: Python's ``datetime.date`` range (years 1..9999).
      Validation goes through ``datetime.date``, comparison through
      ``datetime.date``, and Period arithmetic through ``relativedelta``,
      exactly as the solver did before the unbounded default existed. Results of
      Period arithmetic on a bounded Date are bounded too, and raise if they
      leave the range, as ``datetime`` does.
    """

    def __init__(self, year: int, month: int, day: int, bounded: bool = False):
        """Initialize a Date with year, month, day components.

        Args:
            year: Year component (any integer)
            month: Month component
            day: Day component
            bounded: If True, the date lives in Python's datetime.date range
                     (years 1..9999) and all operations go through datetime.
                     Results of Period arithmetic on a bounded Date are bounded too.
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

    @property
    def bounded(self) -> bool:
        """Whether this Date is restricted to Python's year range 1..9999."""
        return self._bounded

    def _validate(self) -> None:
        """Validate that the date components are valid."""
        # Validate input format first: all components must be integers (no bools allowed)
        date_components = (self._year, self._month, self._day)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in date_components):
            raise ValueError(
                "Invalid date format: year, month, and day must be integers"
            )

        if self._bounded:
            # Python path: datetime.date validates calendar correctness and the
            # range 1..9999 together.
            try:
                date(self._year, self._month, self._day)
            except ValueError as e:
                raise ValueError(
                    f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
                ) from e
            return

        # Integer path: calendar correctness in the proleptic Gregorian calendar,
        # for any year.
        if not (1 <= self._month <= 12
                and 1 <= self._day <= concrete_days_in_month(self._year, self._month)):
            raise ValueError(
                f"Invalid date: {self._year}-{self._month:02d}-{self._day:02d}"
            )

    def __str__(self) -> str:
        """Return a string representation of the Date."""
        return f"Date({self.year}, {self.month}, {self.day})"

    def __hash__(self) -> int:
        """Return hash value for Date object."""
        return hash((self.year, self.month, self.day))

    def _ymd(self) -> Tuple[int, int, int]:
        return (self._year, self._month, self._day)

    def _cmp_key(self, other: "Date"):
        """Comparison keys: datetime.date objects when both are bounded (the Python
        path), (y, m, d) tuples otherwise. Both orders agree."""
        if self._bounded and other._bounded:
            return self.to_python_date(), other.to_python_date()
        return self._ymd(), other._ymd()

    @staticmethod
    def _defer_to(other) -> bool:
        """Whether a comparison with `other` should be handled by its reflected method.

        Includes: symbolic DateVar and EvalDateVar (validation).
        """
        other_cls = other.__class__
        other_name = other_cls.__name__
        return (other_name in ("DateVar", "EvalDateVar") or
                (other_name == "DateVar" and getattr(other_cls, "__module__", "").startswith("datesat.symbolic")))

    def __eq__(self, other: "Date") -> bool:
        """Check if two dates are equal."""
        if isinstance(other, Date):
            return self._ymd() == other._ymd()
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __ne__(self, other: "Date") -> bool:
        """Check if two dates are not equal."""
        if isinstance(other, Date):
            return self._ymd() != other._ymd()
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __lt__(self, other: "Date"):
        """Check if this date is less than another."""
        if isinstance(other, Date):
            a, b = self._cmp_key(other)
            return a < b
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __le__(self, other: "Date"):
        """Check if this date is less than or equal to another."""
        if isinstance(other, Date):
            a, b = self._cmp_key(other)
            return a <= b
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __gt__(self, other: "Date"):
        """Check if this date is greater than another."""
        if isinstance(other, Date):
            a, b = self._cmp_key(other)
            return a > b
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def __ge__(self, other: "Date"):
        """Check if this date is greater than or equal to another."""
        if isinstance(other, Date):
            a, b = self._cmp_key(other)
            return a >= b
        if self._defer_to(other):
            return NotImplemented
        raise TypeError(f"Cannot compare Date with {type(other)}")

    def to_python_date(self) -> date:
        """Convert to Python date object. Raises ValueError outside years 1..9999."""
        return date(self.year, self.month, self.day)

    @classmethod
    def from_python_date(cls, d: date, bounded: bool = False) -> "Date":
        """Create Date from Python date object."""
        return cls(d.year, d.month, d.day, bounded=bounded)

    def to_days(self) -> int:
        """Days since 1970-01-01 (proleptic Gregorian, any year)."""
        return days_from_civil(self._year, self._month, self._day)

    @classmethod
    def from_days(cls, days: int, bounded: bool = False) -> "Date":
        """Date from days since 1970-01-01 (proleptic Gregorian, any year)."""
        return cls(*civil_from_days(days), bounded=bounded)

    def __add__(self, other: "Period"):
        """
        Date + Period with the solver's semantics: add years and months, clamp the
        day to the end of the resulting month, then add days.

        Bounded Dates use datetime + relativedelta (the original implementation),
        which raises when the result, or the mid-step after adding years and
        months, leaves years 1..9999. Unbounded Dates use plain integers, so the
        result is defined for every year.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to Date")

        if self._bounded:
            py_date = self.to_python_date()
            result_date = py_date + relativedelta(
                years=other.years, months=other.months, days=other.days
            )
            return Date.from_python_date(result_date, bounded=True)

        total_months = self._year * 12 + (self._month - 1) + other.years * 12 + other.months
        y, m0 = divmod(total_months, 12)
        m = m0 + 1
        d = min(self._day, concrete_days_in_month(y, m))
        if other.days:
            y, m, d = civil_from_days(days_from_civil(y, m, d) + other.days)
        return Date(y, m, d, bounded=self._bounded)

    def __sub__(self, other: "Period"):
        """Date - Period implemented as Date + (-Period)."""
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

        # Period range bounds removed - any integer period is allowed.
        # Previously constrained to fit within the allowed date range:
        # if abs(years) > self.MAX_PERIOD_YEARS:
        #     raise ValueError(
        #         f"Period years out of range: {years} (max ±{self.MAX_PERIOD_YEARS})"
        #     )
        # if abs(months) > self.MAX_PERIOD_MONTHS:
        #     raise ValueError(
        #         f"Period months out of range: {months} (max ±{self.MAX_PERIOD_MONTHS})"
        #     )
        # if abs(days) > self.MAX_PERIOD_DAYS:
        #     raise ValueError(
        #         f"Period days out of range: {days} (max ±{self.MAX_PERIOD_DAYS})"
        #     )

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
