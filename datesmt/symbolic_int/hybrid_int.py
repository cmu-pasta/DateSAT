"""
Hybrid DATE-SMT implementation using dual-lazy representation.

This module implements a hybrid approach where dates can be represented by
either epoch days or (Y, M, D), and each side is materialized and kept
consistent lazily on demand:
- epoch_var: Z3 Int, days since 2000-03-01
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
    And,
    ArithRef,
    BoolRef,
    CheckSatResult,
    If,
    Int,
    IntVal,
    ModelRef,
    Not,
    Or,
    Solver,    sat,
    unsat,
    unknown,
)
from ..core import Date, Period, _UnboundedDate
from .naive_int import (
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
from .epoch_days_int import from_days_since_epoch, to_days_since_epoch


class DateVar:
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str):
        """Create a symbolic date variable."""
        self.ctx = ctx
        self.name = name
        # Primary epoch representation
        self.epoch_var = Int(f"{name}_epoch")
        # Lazy YMD vars
        self._ymd_exists = False
        self._year_var = None
        self._month_var = None
        self._day_var = None
        # Consistency flags: which representation reflects the current value
        self._epoch_consistent = True   # epoch_var starts as the source of truth
        self._ymd_consistent = False    # Y/M/D not yet materialized/consistent

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    # Back-compat property name used in some places
    @property
    def days_var(self) -> ArithRef:
        return self.epoch_var

    @property
    def year_var(self) -> ArithRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._year_var

    @property
    def month_var(self) -> ArithRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._month_var

    @property
    def day_var(self) -> ArithRef:
        if not self._ymd_exists:
            self._ensure_ymd()
        return self._day_var

    # Alias properties for compatibility with parser-generated code
    # The parser generates code like "x.year == y" which expects .year attribute
    @property
    def year(self) -> ArithRef:
        """Alias for year_var for compatibility with parser-generated code."""
        return self.year_var

    @property
    def month(self) -> ArithRef:
        """Alias for month_var for compatibility with parser-generated code."""
        return self.month_var

    @property
    def day(self) -> ArithRef:
        """Alias for day_var for compatibility with parser-generated code."""
        return self.day_var

    def to_concrete_date(self, model: ModelRef) -> Date:
        if self._ymd_consistent and self._ymd_exists:
            y = model.evaluate(self._year_var, model_completion=True).as_long()
            m = model.evaluate(self._month_var, model_completion=True).as_long()
            d = model.evaluate(self._day_var, model_completion=True).as_long()
            return Date(y, m, d)
        # Otherwise evaluate epoch expression and decode
        e = model.evaluate(self._epoch_expr(), model_completion=True).as_long()
        return from_days_since_epoch(e)

    # ----- Internal helpers -----
    def _ensure_ymd(self) -> None:
        if self._ymd_exists:
            return
        self._year_var = Int(f"{self.name}_year")
        self._month_var = Int(f"{self.name}_month")
        self._day_var = Int(f"{self.name}_day")
        self._ymd_exists = True
        # Add validity constraints
        self.ctx._add_date_constraints(self)
        # Link YMD to epoch: When YMD is materialized, it becomes the source of truth
        # Add constraint: epoch_var == days_since_epoch_from_ymd(year_var, month_var, day_var)
        self.ctx.solver.add(self.epoch_var == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var))
        # Update consistency flags: YMD is now the consistent representation
        self._ymd_consistent = True
        self._epoch_consistent = False

    def _epoch_expr(self) -> ArithRef:
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

    def _ymd_expr(self) -> Tuple[ArithRef, ArithRef, ArithRef]:
        """Return Y/M/D expressions consistent with current state (lazy)."""
        if self._ymd_consistent and self._ymd_exists:
            return self._year_var, self._month_var, self._day_var
        # derive from epoch lazily
        return ymd_from_days_since_epoch(self._epoch_expr())

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison.

        Comparison strategy (dual-lazy):
        1. If both have consistent Y/M/D: compare lexicographically on (Y, M, D)
        2. Else if both have consistent epoch: compare on epoch_var
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, (Date, _UnboundedDate)):
            return self._epoch_expr() >= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    y1 > y2,
                    And(y1 == y2, Or(m1 > m2, And(m1 == m2, d1 >= d2)))
                )
            # Case 2: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var >= other.epoch_var
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            # (this handles: epoch vs Y/M/D, epoch vs epoch (but one inconsistent), etc.)
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
        if isinstance(other, (Date, _UnboundedDate)):
            return self._epoch_expr() <= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    y1 < y2,
                    And(y1 == y2, Or(m1 < m2, And(m1 == m2, d1 <= d2)))
                )
            # Case 2: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var <= other.epoch_var
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            return self._epoch_expr() <= other._epoch_expr()
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other) -> BoolRef:
        """Support x < date comparison."""
        if isinstance(other, (Date, _UnboundedDate, DateVar)):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other) -> BoolRef:
        """Support x > date comparison."""
        if isinstance(other, (Date, _UnboundedDate, DateVar)):
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
        if isinstance(other, _UnboundedDate):
            raise ValueError(
                f"Cannot constrain date variable to equal Date({other.year}, {other.month}, {other.day}) "
                f"which is outside the allowed range [1900-03-01..2100-02-28]. "
                f"This constraint is always unsatisfiable."
            )
        elif isinstance(other, Date):
            return self._epoch_expr() == to_days_since_epoch(other)
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
        if isinstance(other, _UnboundedDate):
            # Date variable can never equal an out-of-range date, so != is always true
            from z3 import BoolVal
            return BoolVal(True)
        elif isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

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
            self.ctx.solver.add(result.epoch_var == self._epoch_expr() + IntVal(other.days))
            # Result now has epoch consistent; YMD not yet
            result._epoch_consistent = True
            result._ymd_consistent = False
            return result

        # Extract period components as Z3 terms
        if isinstance(other, Period):
            oy, om, od = IntVal(other.years), IntVal(other.months), IntVal(other.days)
        else:
            oy, om, od = other.years, other.months, other.days

        # Get base Y/M/D terms lazily from whichever side is consistent
        y0, m0, d0 = self._ymd_expr()
        # Step 1: combine years/months with AMI normalization
        period_total_months = oy * IntVal(12) + om
        total_months = m0 + period_total_months
        year_carry, m1 = normalize_month(IntVal(0), total_months)
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

    def __init__(self, timeout_ms=600000):
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
        self.solver.add(dv.epoch_var >= -36525)
        self.solver.add(dv.epoch_var <= 36523)
        return dv

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
        elif result == unsat:
            return {'status': 'unsat', 'dates': {}}
        else:
            # result == unknown (timeout or resource limit)
            return {'status': 'timeout', 'dates': {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self) -> List[BoolRef]:
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())

    def _add_date_constraints(self, dv: DateVar) -> None:
        if not dv._ymd_exists:
            return
        Y, M, D = dv._year_var, dv._month_var, dv._day_var
        # Year bounds consistent with epoch bounds
        Y_MIN, Y_MAX = 1900, 2100
        self.solver.add(
            And(
                Y >= Y_MIN,
                Y <= Y_MAX,
                M >= 1,
                M <= 12,
                D >= 1,
                D <= days_in_month(Y, M),
            )
        )
