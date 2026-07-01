"""
Bounded Date and Period classes for future_work.datesat_bounded.

datesat.core.Date and datesat.core.Period no longer enforce the historical
[1900-03-01, 2100-02-28] range. The bounded solvers under
future_work.datesat_bounded.* still need range enforcement at the type level,
so this module provides subclasses that reinstate the range checks.

Because these are subclasses of the base Date/Period, an instance of BoundedDate
also satisfies isinstance(x, datesat.core.Date). That lets the bounded solvers'
existing isinstance checks continue to accept both bounded and unbounded literals
at the interface, while the solver-side _add_bounds() still constrains the SAT
variable to the supported range.
"""

from datesat.core import Date as _BaseDate, Period as _BasePeriod


class Date(_BaseDate):
    """Bounded Date: raises if the date is outside [1900-03-01, 2100-02-28]."""

    _MIN_ALLOWED = (1900, 3, 1)
    _MAX_ALLOWED = (2100, 2, 28)

    def __init__(self, year: int, month: int, day: int, bounded: bool = True):
        # Run the base constructor first (calendar validity + attribute wiring).
        super().__init__(year, month, day, bounded=bounded)
        if bounded:
            components = (year, month, day)
            if components < self._MIN_ALLOWED or components > self._MAX_ALLOWED:
                raise ValueError(
                    f"Date outside allowed range: {year}-{month:02d}-{day:02d} (allowed [1900-03-01..2100-02-28])"
                )

    @classmethod
    def from_python_date(cls, d) -> "Date":
        return cls(d.year, d.month, d.day)

    def __add__(self, other):
        """Date + Period; result must remain within [1900-03-01, 2100-02-28]."""
        if not isinstance(other, _BasePeriod):
            raise TypeError(f"Cannot add {type(other)} to Date")
        result = super().__add__(other)
        # Rewrap so the result carries the bounded check (may raise here).
        return Date(result.year, result.month, result.day)

    def __sub__(self, other):
        """Date - Period implemented as Date + (-Period)."""
        if not isinstance(other, _BasePeriod):
            raise TypeError(f"Cannot subtract {type(other)} from Date")
        neg = Period(-other.years, -other.months, -other.days)
        return self.__add__(neg)


class Period(_BasePeriod):
    """Bounded Period: raises if |years| > 200, |months| > 2400, or |days| > 73048."""

    MAX_PERIOD_DAYS = 73048  # abs(EPOCH_DAYS_MAX - EPOCH_DAYS_MIN) = abs(36523 - (-36525))
    MAX_PERIOD_YEARS = 200  # YEAR_MAX - YEAR_MIN = 2100 - 1900
    MAX_PERIOD_MONTHS = 2400  # MAX_PERIOD_YEARS * 12

    def __init__(self, years: int, months: int, days: int):
        super().__init__(years, months, days)
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

    def __mul__(self, other: int) -> "Period":
        if isinstance(other, int):
            return Period(self.years * other, self.months * other, self.days * other)
        raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __rmul__(self, other: int) -> "Period":
        if isinstance(other, int):
            return self.__mul__(other)
        raise TypeError(f"Cannot multiply Period with {type(other)}")

    def __add__(self, other: "Period") -> "Period":
        if isinstance(other, _BasePeriod):
            return Period(
                self.years + other.years,
                self.months + other.months,
                self.days + other.days,
            )
        return NotImplemented

    def __sub__(self, other: "Period") -> "Period":
        if isinstance(other, _BasePeriod):
            return Period(
                self.years - other.years,
                self.months - other.months,
                self.days - other.days,
            )
        return NotImplemented
