"""
Simple_new DateSAT implementation: the simple encoding with day addition
unrolled along the semantics' transition rules.

Dates are (year, month, day) triples and year/month addition is the same as in
the simple encoding. Day addition differs: simple adds days one at a time
(|n| nested steps), while simple_new unrolls the ADD-DAYS, ADD-DAYS-OVER,
ADD-DAYS-UNDER1 and ADD-DAYS-UNDER2 rules of the semantics (proofs/src/semantics.rs,
Date::add_days), which move a whole month per step. The number of days still
to add becomes symbolic after the first step, and the unrolling needs
O(|n| / 28) steps.
"""

from typing import Tuple

from z3 import And, ArithRef, IntVal, If

from ..core import Period
from . import simple_int
from .simple_int import days_in_month, eom_clamp, normalize_month


def _next_month(y, m) -> Tuple[ArithRef, ArithRef]:
    """The year and month after (y, m)."""
    wrap = m == 12
    return If(wrap, y + 1, y), If(wrap, IntVal(1), m + 1)


def _prev_month(y, m) -> Tuple[ArithRef, ArithRef]:
    """The year and month before (y, m)."""
    wrap = m == 1
    return If(wrap, y - 1, y), If(wrap, IntVal(12), m - 1)


def _add_days_steps(delta_days: int) -> int:
    """
    Steps of the unrolling that reach ADD-DAYS for any valid start date.

    n > 0: one ADD-DAYS-OVER from the start day, then one per month from day 1,
    each consuming at least 28 days, then ADD-DAYS.
    n < 0: one ADD-DAYS-UNDER1 to day 1, then one ADD-DAYS-UNDER2 per month,
    each giving back at least 28 days, then ADD-DAYS.
    """
    return abs(delta_days) // 28 + 3


def add_days_semantics(y, m, d, delta_days: int) -> Tuple[ArithRef, ArithRef, ArithRef]:
    """
    Add a concrete day offset by unrolling the semantics' day-addition rules.

    The state is (y, m, d, n) with n the days still to add. Each step applies the
    rule whose premise holds; ADD-DAYS sets n to 0, after which every step is the
    identity. The sign of n decides which rules can fire: from n > 0 only ADD-DAYS
    and ADD-DAYS-OVER (n stays >= 0), from n < 0 only ADD-DAYS, ADD-DAYS-UNDER1 and
    ADD-DAYS-UNDER2, so only those are encoded.
    """
    if delta_days == 0:
        return y, m, d

    zero, one = IntVal(0), IntVal(1)
    cur_y, cur_m, cur_d, n = y, m, d, IntVal(delta_days)

    for _ in range(_add_days_steps(delta_days)):
        dim = days_in_month(cur_y, cur_m)
        target = cur_d + n
        if delta_days > 0:
            # ADD-DAYS-OVER: the 1st of the next month, with the days past this month left
            over = target > dim
            ny, nm = _next_month(cur_y, cur_m)
            new_y = If(over, ny, cur_y)
            new_m = If(over, nm, cur_m)
            new_d = If(over, one, target)
            new_n = If(over, n - (dim - cur_d) - 1, zero)
        else:
            in_month = target >= 1
            # ADD-DAYS-UNDER1: back to the 1st of this month
            under1 = And(target < 1, cur_d > 1)
            # ADD-DAYS-UNDER2: from the 1st, to the 1st of the previous month
            py, pm = _prev_month(cur_y, cur_m)
            new_y = If(in_month, cur_y, If(under1, cur_y, py))
            new_m = If(in_month, cur_m, If(under1, cur_m, pm))
            new_d = If(in_month, target, one)
            new_n = If(in_month, zero, If(under1, cur_d - 1 + n, n + days_in_month(py, pm)))
        cur_y, cur_m, cur_d, n = new_y, new_m, new_d, new_n

    return cur_y, cur_m, cur_d


class DateVar(simple_int.DateVar):
    """Symbolic date variable for the simple_new implementation."""

    def __add__(self, other) -> "DateVar":
        """
        DateVar + Period following the semantics' ADD-PERIOD rule:
        1) Combine Y and M (normalize months into 1..12 with year carry)
        2) Apply EOM clamp: day := min(original_day, days_in_month(new_year,new_month))
        3) Add D days by unrolling the day-addition rules (add_days_semantics)

        A days-only period skips steps 1 and 2, which are the identity on valid dates.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to DateVar")
        result = DateVar(f"{self.name}_plus")

        if other.years == 0 and other.months == 0:
            y1, m1, d1 = self.year, self.month, self.day
        else:
            period_total_months = IntVal(other.years) * IntVal(12) + IntVal(other.months)
            year_carry, m1 = normalize_month(IntVal(0), self.month + period_total_months)
            y1 = self.year + year_carry
            d1 = eom_clamp(y1, m1, self.day)

        result.year, result.month, result.day = add_days_semantics(y1, m1, d1, other.days)

        # Add bounds to intermediate result
        result._solver = self._solver
        result._python_bounds = self._python_bounds
        result._add_bounds()
        return result


class SimpleNewSolver(simple_int.SimpleSolver):
    """Simple date constraint solver whose day addition follows the semantics' rules."""

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with comprehensive date validation."""
        date_var = DateVar(name)
        date_var._solver = self.solver
        date_var._python_bounds = self.python_bounds
        self.date_vars[name] = date_var

        # Add bounds using _add_bounds method
        date_var._add_bounds()
        return date_var
