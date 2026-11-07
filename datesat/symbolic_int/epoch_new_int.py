"""
Epoch_new DateSAT implementation: the epoch_days encoding with the closed-form
year-of-era decoder.

Dates are days since 2000-03-01, as in epoch_days. The only difference is the
conversion from days back to (year, month, day). epoch_days peels centuries,
4-year blocks and years off the day of the 400-year era by Euclidean division
by 36524, 1461 and 365, clamping two quotients. epoch_new instead computes the
year of the era with Hinnant's single expression

    yoe = (doe - doe/1460 + doe/36524 - doe/146096) / 365

and the day of that year as doe - (365*yoe + yoe/4 - yoe/100), as the proofs
specified EpochDelta::to_ymd before commit 061ed60.
"""

from typing import Tuple

from z3 import ArithRef, If, IntVal

from ..core import Period
from . import epoch_days_int
from .epoch_days_int import add_days_ordinal, days_since_epoch_from_ymd
from .simple_int import eom_clamp, normalize_month


def _ymd_from_days_since_epoch_z3(days_term: ArithRef) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """Decode (y,m,d) from a Z3 Int 'days since 2000-03-01' with the closed-form year of era."""
    # Split into 400-year eras (Z3 div/mod with positive divisor gives 0 <= doe < 146097)
    era = days_term / IntVal(146097)
    doe = days_term % IntVal(146097)

    # March-based year of the era (0..399): remove the leap days elapsed, then divide by 365
    yoe = (doe - doe / IntVal(1460) + doe / IntVal(36524) - doe / IntVal(146096)) / IntVal(365)

    # Day of that March-based year (0..365)
    doy = doe - (IntVal(365) * yoe + yoe / IntVal(4) - yoe / IntVal(100))

    # Convert March-based day-of-year to month/day using 153-day month blocks
    # mp: 0..11 corresponds to Mar..Feb
    mp = (IntVal(5) * doy + IntVal(2)) / IntVal(153)
    d = doy - (IntVal(153) * mp + IntVal(2)) / IntVal(5) + IntVal(1)
    m = mp + IntVal(3)                 # Mar=3,...,Dec=12,Jan=13,Feb=14
    m = If(m > IntVal(12), m - IntVal(12), m)  # wrap Jan/Feb back to 1/2

    # If month is Jan/Feb, it belongs to the next Gregorian year
    y = IntVal(2000) + era * IntVal(400) + yoe + If(m <= IntVal(2), IntVal(1), IntVal(0))

    return y, m, d


class DateVar(epoch_days_int.DateVar):
    """Symbolic date variable for the epoch_new implementation."""

    @property
    def year(self) -> ArithRef:
        """Get symbolic year component (decodes from days_var)."""
        y, _, _ = _ymd_from_days_since_epoch_z3(self.days_var)
        return y

    @property
    def month(self) -> ArithRef:
        """Get symbolic month component (decodes from days_var)."""
        _, m, _ = _ymd_from_days_since_epoch_z3(self.days_var)
        return m

    @property
    def day(self) -> ArithRef:
        """Get symbolic day component (decodes from days_var)."""
        _, _, d = _ymd_from_days_since_epoch_z3(self.days_var)
        return d

    def __add__(self, other) -> "DateVar":
        """
        DateVar + Period following semantics.
        Steps: normalize Y/M, EOM clamp, then add D days in ordinal space.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to DateVar")
        result = DateVar(f"{self.name}_plus")

        # Fast-path: only days component (check at Python level since Period components are concrete)
        if other.years == 0 and other.months == 0:
            days_expr = self.days_var + IntVal(other.days)
        else:
            # Decode current date to Y/M/D
            y0, m0, d0 = _ymd_from_days_since_epoch_z3(self.days_var)

            # Step 1: Combine Y and M with normalization (carry years)
            period_total_months = IntVal(other.years) * IntVal(12) + IntVal(other.months)
            y1, m1 = normalize_month(y0, m0 + period_total_months)

            # Step 2: EOM clamp
            d1 = eom_clamp(y1, m1, d0)

            if other.days == 0:
                # Encode back to days-since-epoch
                days_expr = days_since_epoch_from_ymd(y1, m1, d1)
            else:
                # Step 3: add D days in ordinal space
                days_expr = add_days_ordinal(y1, m1, d1, IntVal(other.days))

        result.days_var = days_expr

        # Add bounds to intermediate result
        result._solver = self._solver
        result._python_bounds = self._python_bounds
        result._add_bounds()
        return result


class EpochNewSolver(epoch_days_int.EpochDaysSolver):
    """Epoch_days date constraint solver with the closed-form year-of-era decoder."""

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        date_var._solver = self.solver
        date_var._python_bounds = self.python_bounds
        self.date_vars[name] = date_var

        # Add bounds using _add_bounds method
        date_var._add_bounds()
        return date_var
