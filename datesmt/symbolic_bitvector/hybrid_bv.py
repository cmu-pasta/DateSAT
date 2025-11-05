"""
Hybrid DATE-SMT implementation using dual-lazy representation.

This module implements a hybrid approach where dates can be represented by
either epoch days or (Y, M, D), and each side is materialized and kept
consistent lazily on demand:
- epoch_var: Z3 BitVec, days since 2000-03-01
- year/month/day vars: created lazily when needed

Rules:
- We track which representation is currently consistent via flags.
- No automatic forward-link is added when Y/M/D are materialized.
- When an operation requires epoch, we use the epoch expression derived from
  whichever side is currently consistent.
- When an operation requires Y/M/D, we use Y/M/D terms derived similarly.
- Comparisons prefer Y/M/D when both sides have consistent Y/M/D; otherwise
  prefer epoch if both have consistent epoch; otherwise derive epoch terms
  on the fly and compare.
"""

from typing import Union, Tuple, List
from datetime import date, timedelta
from z3 import (
    UGE,
    ULE,
    UGT,
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
from .bitwidths import LEGACY_BITS
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
        self.epoch_var = BitVec(f"{name}_epoch", LEGACY_BITS)
        # Lazy YMD vars
        self._ymd_exists = False
        self._year_var = None
        self._month_var = None
        self._day_var = None
        # Consistency flags
        self._epoch_consistent = True
        self._ymd_consistent = False

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
        self._year_var = BitVec(f"{self.name}_year", LEGACY_BITS)
        self._month_var = BitVec(f"{self.name}_month", LEGACY_BITS)
        self._day_var = BitVec(f"{self.name}_day", LEGACY_BITS)
        self._ymd_exists = True
        # Add validity constraints, but do NOT link to epoch automatically
        self.ctx._add_date_constraints(self)

    def _epoch_expr(self) -> BitVecRef:
        """Return an epoch-days expression consistent with current state (lazy).
        
        If epoch is consistent, return epoch_var directly.
        Otherwise, derive epoch from Y/M/D (Y/M/D must exist when epoch_consistent is False).
        """
        if self._epoch_consistent:
            return self.epoch_var
        # derive from Y/M/D lazily
        # Invariant: if _epoch_consistent is False, _ymd_exists should be True
        # (because we only set _epoch_consistent=False after creating Y/M/D in month/year operations)
        return days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)

    def _ymd_expr(self) -> tuple[BitVecRef, BitVecRef, BitVecRef]:
        if self._ymd_consistent and self._ymd_exists:
            return self._year_var, self._month_var, self._day_var
        return ymd_from_days_since_epoch(self._epoch_expr())

    def to_concrete_date(self, model: ModelRef) -> Date:
        if self._ymd_consistent and self._ymd_exists:
            y = model.evaluate(self._year_var, model_completion=True).as_signed_long()
            m = model.evaluate(self._month_var, model_completion=True).as_signed_long()
            d = model.evaluate(self._day_var, model_completion=True).as_signed_long()
            return Date(y, m, d)
        e = model.evaluate(self._epoch_expr(), model_completion=True).as_signed_long()
        return from_days_since_epoch(e)

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison.
        
        Comparison strategy (dual-lazy):
        1. If both have consistent Y/M/D: compare lexicographically on (Y, M, D)
        2. Else if both have consistent epoch: compare on epoch_var
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            # Use signed comparison for epoch values (can be negative)
            return self._epoch_expr() >= BitVecVal(to_days_since_epoch(other), LEGACY_BITS)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    UGT(y1, y2),
                    And(y1 == y2, Or(UGT(m1, m2), And(m1 == m2, UGE(d1, d2))))
                )
            # Case 2: Both have consistent epoch - use signed epoch comparison (can be negative)
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var >= other.epoch_var
            # Case 3: Inconsistent - derive epoch expressions for both and compare (signed, can be negative)
            return self._epoch_expr() >= other._epoch_expr()
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison.
        
        Comparison strategy (dual-lazy):
        1. If both have consistent Y/M/D: compare lexicographically on (Y, M, D)
        2. Else if both have consistent epoch: compare on epoch_var
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            # Use signed comparison for epoch values (can be negative)
            return self._epoch_expr() <= BitVecVal(to_days_since_epoch(other), LEGACY_BITS)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    ULT(y1, y2),
                    And(y1 == y2, Or(ULT(m1, m2), And(m1 == m2, ULE(d1, d2))))
                )
            # Case 2: Both have consistent epoch - use signed epoch comparison (can be negative)
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var <= other.epoch_var
            # Case 3: Inconsistent - derive epoch expressions for both and compare (signed, can be negative)
            return self._epoch_expr() <= other._epoch_expr()
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
        """Support x == date comparison.
        
        Comparison strategy (dual-lazy):
        1. If both have consistent Y/M/D: compare on (Y, M, D) components
        2. Else if both have consistent epoch: compare on epoch_var
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            return self._epoch_expr() == BitVecVal(to_days_since_epoch(other), LEGACY_BITS)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                return And(
                    self._year_var == other._year_var,
                    self._month_var == other._month_var,
                    self._day_var == other._day_var,
                )
            # Case 2: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var == other.epoch_var
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            return self._epoch_expr() == other._epoch_expr()
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
                result.epoch_var == self._epoch_expr() + BitVecVal(other.days, LEGACY_BITS)
            )
            result._epoch_consistent = True
            result._ymd_consistent = False
            return result

        # Extract period components as Z3 terms
        if isinstance(other, Period):
            oy, om, od = (
                BitVecVal(other.years, LEGACY_BITS),
                BitVecVal(other.months, LEGACY_BITS),
                BitVecVal(other.days, LEGACY_BITS),
            )
        else:
            oy, om, od = other.years, other.months, other.days

        # Get base Y/M/D terms lazily from whichever side is consistent
        y0, m0, d0 = self._ymd_expr()
        # Step 1: combine years/months with AMI normalization
        period_total_months = oy * BitVecVal(12, LEGACY_BITS) + om
        total_months = m0 + period_total_months
        year_carry, m1 = normalize_month(BitVecVal(0, LEGACY_BITS), total_months)
        y1 = y0 + year_carry
        # Step 2: EOM clamp
        d1 = eom_clamp(y1, m1, d0)
        # Step 3: add days in ordinal space
        y2, m2, d2 = add_days_ordinal(y1, m1, d1, od)
        # Constrain result Y/M/D only; leave epoch to be derived on demand
        self.ctx.solver.add(result.year_var == y2)
        self.ctx.solver.add(result.month_var == m2)
        self.ctx.solver.add(result.day_var == d2)
        result._ymd_consistent = True
        result._epoch_consistent = False
        return result

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
        self.solver.add(dv.epoch_var >= BitVecVal(-36525, LEGACY_BITS))
        self.solver.add(dv.epoch_var <= BitVecVal(36523, LEGACY_BITS))
        return dv

    def _add_date_constraints(self, dv: DateVar) -> None:
        if not dv._ymd_exists:
            return
        Y, M, D = dv._year_var, dv._month_var, dv._day_var
        # Year bounds consistent with epoch bounds
        Y_MIN, Y_MAX = 1900, 2100
        self.solver.add(
            And(
                Y >= BitVecVal(Y_MIN, LEGACY_BITS),
                Y <= BitVecVal(Y_MAX, LEGACY_BITS),
                M >= BitVecVal(1, LEGACY_BITS),
                M <= BitVecVal(12, LEGACY_BITS),
                D >= BitVecVal(1, LEGACY_BITS),
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
