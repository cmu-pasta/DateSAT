"""
Hybrid DATE-SMT implementation using dual representation.

This module implements the hybrid approach where dates are represented
using dual representation: epoch-primary, YMD-derived. Each date has:
- epoch_var: Z3 Int, days since 2000-03-01 (primary for comparisons/day ops)
- year/month/day vars: created lazily when needed; with a forward link
  epoch_var == days_since_epoch_from_ymd(year, month, day)

Comparisons and day arithmetic use O(1) epoch operations; month/year
arithmetic uses simple AMI on (Y,M,D) components without re-encoding to
epoch unless needed. Period addition matches epoch_days semantics but avoids
encoding back to epoch when not necessary.
"""

from typing import Union, Tuple, List
from datetime import date, timedelta
from z3 import (
    UGE,
    ULT,
    And,
    ArithRef,
    BitVecRef,
    BoolRef,
    CheckSatResult,
    If,
    BitVec,
    BitVecVal,
    ModelRef,
    Not,
    Or,
    Solver,
    sat
)
from ..core import Date, Period
from .baseline_bv import (
    is_leap,
    days_in_month,
    normalize_month,
    days_before_year,
    days_before_month,
    to_ordinal,
    from_ordinal,
    ymd_from_days_since_epoch,
    days_since_epoch_from_ymd, 
    eom_clamp, 
    add_days_ordinal,
    _dbm_index,
)
from .epoch_days_bv import from_days_since_epoch, to_days_since_epoch


class DateVar:
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str):
        self.ctx = ctx
        self.name = name
        # Primary epoch representation
        self.epoch_var = BitVec(f"{name}_epoch", 32)
        # Lazy YMD vars
        self._ymd_exists = False
        self._year_var = None
        self._month_var = None
        self._day_var = None
        self._forward_link_added = False
        # Tracks whether epoch_var and (Y,M,D) are linked for this var
        self._epoch_ymd_consistent = False

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    # Back-compat property name used in some places
    @property
    def days_var(self) -> BitVecRef:
        return self.epoch_var

    @property
    def year_var(self) -> BitVecRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._year_var

    @property
    def month_var(self) -> BitVecRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._month_var

    @property
    def day_var(self) -> BitVecRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._day_var

    def _ensure_ymd(self) -> None:
        if self._ymd_exists:
            return
        self._year_var = BitVec(f"{self.name}_year", 32)
        self._month_var = BitVec(f"{self.name}_month", 32)
        self._day_var = BitVec(f"{self.name}_day", 32)
        self._ymd_exists = True
        # Add validity constraints
        self.ctx._add_date_constraints(self)
        # Add forward link
        self._add_forward_link()

    def _add_forward_link(self) -> None:
        if self._forward_link_added:
            return
        self.ctx.solver.add(
            self.epoch_var
            == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)
        )
        self._forward_link_added = True
        self._epoch_ymd_consistent = True

    def to_concrete_date(self, model: ModelRef) -> Date:
        if self._ymd_exists:
            y = model.evaluate(self._year_var, model_completion=True).as_signed_long()
            m = model.evaluate(self._month_var, model_completion=True).as_signed_long()
            d = model.evaluate(self._day_var, model_completion=True).as_signed_long()
            return Date(y, m, d)
        else:
            e = model.evaluate(self.epoch_var, model_completion=True).as_signed_long()
            return from_days_since_epoch(e)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            return self.epoch_var >= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.epoch_var >= other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            return self.epoch_var <= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.epoch_var <= other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other) -> BoolRef:
        """Support x < date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other) -> BoolRef:
        """Support x > date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other) -> BoolRef:
        """Support x == date comparison."""
        if isinstance(other, Date):
            return self.epoch_var == to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            return self.epoch_var == other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison."""
        return Not(self.__eq__(other))

    def __add__(self, other) -> 'DateVar':
        """Hybrid date + Period: mirror epoch_days semantics, but avoid epoch encode unless days-only.

        - days-only: epoch add (O(1))
        - months/years (and mixed): decode epoch→YMD, normalize months, clamp, add days via ordinal,
          then set result's Y/M/D; epoch derives later when needed.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to DateVar")

        result = self.ctx.add_date_var(f"{self.name}_plus")

        # Concrete Period fast-path for days-only
        if isinstance(other, Period) and other.years == 0 and other.months == 0:
            self.ctx.solver.add(
                result.epoch_var == self.epoch_var + BitVecVal(other.days, 32)
            )
            return result

        # Extract period components as Z3 terms
        if isinstance(other, Period):
            oy, om, od = (
                BitVecVal(other.years, 32),
                BitVecVal(other.months, 32),
                BitVecVal(other.days, 32),
            )
        else:
            oy, om, od = other.years, other.months, other.days

        # Decode current epoch to Y/M/D (pure Z3 terms), unless we already have
        # materialized, consistent Y/M/D variables for this date
        if self._ymd_exists and self._epoch_ymd_consistent:
            y0, m0, d0 = self._year_var, self._month_var, self._day_var
        else:
            y0, m0, d0 = ymd_from_days_since_epoch(self.epoch_var)
        # Step 1: combine years/months with AMI normalization
        period_total_months = oy * BitVecVal(12, 32) + om
        total_months = m0 + period_total_months
        year_carry, m1 = normalize_month(BitVecVal(0, 32), total_months)
        y1 = y0 + year_carry
        # Step 2: EOM clamp
        d1 = eom_clamp(y1, m1, d0)
        # Step 3: add days in ordinal space
        y2, m2, d2 = add_days_ordinal(y1, m1, d1, od)
        # Constrain result Y/M/D only (epoch will be derived on demand)
        self.ctx.solver.add(result.year_var == y2)
        self.ctx.solver.add(result.month_var == m2)
        self.ctx.solver.add(result.day_var == d2)
        return result

    def __radd__(self, other) -> 'DateVar':
        """Support period + date addition."""
        if isinstance(other, Period):
            return self.__add__(other)
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other) -> 'DateVar':
        """DateVar - Period implemented as DateVar + (-Period)."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class HybridSolver:
    """Hybrid date constraint solver using dual representation (epoch + YMD)."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        if name is None:
            name = f"d{len(self.date_vars)}"
        # Ensure uniqueness to avoid collisions when creating multiple temporaries
        base_name = name
        suffix = 0
        while name in self.date_vars:
            suffix += 1
            name = f"{base_name}_{suffix}"
        dv = DateVar(self, name)
        self.date_vars[name] = dv

        # Basic epoch range constraints [1900-03-01 .. 2100-02-28]
        self.solver.add(dv.epoch_var >= BitVecVal(-36525, 32))
        self.solver.add(dv.epoch_var <= BitVecVal(36523, 32))
        return dv

    def _add_date_constraints(self, dv: DateVar) -> None:
        if not dv._ymd_exists:
            return
        Y, M, D = dv._year_var, dv._month_var, dv._day_var
        # Year bounds consistent with epoch bounds
        Y_MIN, Y_MAX = 1900, 2100
        self.solver.add(
            And(
                Y >= BitVecVal(Y_MIN, 32),
                Y <= BitVecVal(Y_MAX, 32),
                M >= BitVecVal(1, 32),
                M <= BitVecVal(12, 32),
                D >= BitVecVal(1, 32),
                D <= days_in_month(Y, M),
            )
        )

    def add_constraint(self, constraint: BoolRef) -> None:
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

    def solve(self) -> Union[bool, dict]:
        """Solve the constraints."""
        result = self.check()
        if result == sat:
            model = self.model()
            return {
                'status': 'sat',
                'dates': self.get_concrete_dates(model),
            }
        else:
            return {'status': 'unsat', 'dates': {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self) -> List[BoolRef]:
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())
