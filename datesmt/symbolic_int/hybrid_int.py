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
    Optimize,
    Or,
    Solver,    
    sat,
    unsat,
    unknown,
)
from ..core import Date, Period
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
    _dbm_index,
)
from .epoch_days_int import from_days_since_epoch, to_days_since_epoch, add_days_ordinal

class DateVar:
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str, is_user_var: bool = True):
        """Create a symbolic date variable."""
        self.ctx = ctx
        self.name = name
        # Track if this is a user-declared variable (needs bounds) vs intermediate result
        self._is_user_var = is_user_var
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
            try:
                return Date(y, m, d)
            except ValueError:
                # Intermediate result went out of bounds - use unbounded date
                return Date(y, m, d, bounded=False)
        # Otherwise evaluate epoch expression and decode
        e = model.evaluate(self._epoch_expr(), model_completion=True).as_long()
        try:
            return from_days_since_epoch(e)
        except ValueError:
            # Epoch out of bounds - convert to Y/M/D then create unbounded date
            _EPOCH = date(2000, 3, 1)
            result_date = _EPOCH + timedelta(days=e)
            return Date(result_date.year, result_date.month, result_date.day, bounded=False)

    # ----- Internal helpers -----
    def _ensure_ymd(self) -> None:
        """Ensure Y/M/D variables exist. Creates them if they don't exist.
        
        Note: This only creates the vars and links them to epoch. It does NOT
        set consistency flags - that should be done by the caller based on
        which representation is the source of truth.
        """
        if self._ymd_exists:
            return
        self._year_var = Int(f"{self.name}_year")
        self._month_var = Int(f"{self.name}_month")
        self._day_var = Int(f"{self.name}_day")
        self._ymd_exists = True
        # Add validity constraints
        self.ctx._add_date_constraints(self)
        # Link YMD to epoch (bidirectional constraint)
        # Add constraint: epoch_var == days_since_epoch_from_ymd(year_var, month_var, day_var)
        self.ctx.solver.add(self.epoch_var == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var))
        # Note: Consistency flags are NOT set here - caller should set them based on source of truth

    def _epoch_expr(self) -> ArithRef:
        """Return an epoch-days expression consistent with current state (lazy).

        If epoch is consistent, return epoch_var directly.
        Otherwise, derive epoch from Y/M/D (Y/M/D must exist when epoch_consistent is False),
        store it, and update consistency flags.
        """
        if self._epoch_consistent:
            return self.epoch_var
        # derive from Y/M/D lazily
        y, m, d = self._year_var, self._month_var, self._day_var
        epoch_expr = days_since_epoch_from_ymd(y, m, d)
        # Store the derived representation and update consistency
        self.ctx.solver.add(self.epoch_var == epoch_expr)
        self._epoch_consistent = True
        return self.epoch_var

    def _ymd_expr(self) -> Tuple[ArithRef, ArithRef, ArithRef]:
        """Return Y/M/D expressions consistent with current state (lazy).
        
        If Y/M/D is consistent, return Y/M/D vars directly.
        Otherwise, derive Y/M/D from epoch, store them, and update consistency flags.
        """
        if self._ymd_consistent and self._ymd_exists:
            return self._year_var, self._month_var, self._day_var
        # derive from epoch lazily
        epoch = self._epoch_expr()
        y, m, d = ymd_from_days_since_epoch(epoch)
        # Ensure Y/M/D vars exist
        if not self._ymd_exists:
            self._ensure_ymd()
            # _ensure_ymd() links epoch to Y/M/D, but since epoch is source of truth,
            # we need to set Y/M/D values from epoch
            self.ctx.solver.add(self._year_var == y)
            self.ctx.solver.add(self._month_var == m)
            self.ctx.solver.add(self._day_var == d)
        else:
            # Y/M/D vars exist but not consistent - derive and store
            self.ctx.solver.add(self._year_var == y)
            self.ctx.solver.add(self._month_var == m)
            self.ctx.solver.add(self._day_var == d)
        # Update consistency flag
        self._ymd_consistent = True
        return self._year_var, self._month_var, self._day_var

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison.

        Comparison strategy (dual-lazy):
        1. If both have consistent epoch: compare on epoch_var
        2. Else if both have consistent Y/M/D: compare lexicographically on (Y, M, D)
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            # If we have consistent Y/M/D, use Y/M/D comparison (more efficient)
            if self._ymd_consistent and self._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = IntVal(other.year), IntVal(other.month), IntVal(other.day)
                return Or(
                    y1 > y2,
                    And(y1 == y2, Or(m1 > m2, And(m1 == m2, d1 >= d2)))
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() >= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var >= other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    y1 > y2,
                    And(y1 == y2, Or(m1 > m2, And(m1 == m2, d1 >= d2)))
                )
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            return self._epoch_expr() >= other._epoch_expr()
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison.

        Comparison strategy (dual-lazy):
        1. If both have consistent epoch: compare on epoch_var
        2. Else if both have consistent Y/M/D: compare lexicographically on (Y, M, D)
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            # If we have consistent Y/M/D, use Y/M/D comparison (more efficient)
            if self._ymd_consistent and self._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = IntVal(other.year), IntVal(other.month), IntVal(other.day)
                return Or(
                    y1 < y2,
                    And(y1 == y2, Or(m1 < m2, And(m1 == m2, d1 <= d2)))
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() <= to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var <= other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    y1 < y2,
                    And(y1 == y2, Or(m1 < m2, And(m1 == m2, d1 <= d2)))
                )
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            return self._epoch_expr() <= other._epoch_expr()
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other) -> BoolRef:
        """Support x < date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other) -> BoolRef:
        """Support x > date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other) -> BoolRef:
        """Support x == date comparison.

        Comparison strategy (dual-lazy):
        1. If both have consistent epoch: compare on epoch_var
        2. Else if both have consistent Y/M/D: compare on (Y, M, D) components
        3. Else: derive epoch expressions for both sides (converting Y/M/D to epoch if needed) and compare
        """
        if isinstance(other, Date):
            # If we have consistent Y/M/D, use Y/M/D comparison (more efficient)
            if self._ymd_consistent and self._ymd_exists:
                return And(
                    self._year_var == IntVal(other.year),
                    self._month_var == IntVal(other.month),
                    self._day_var == IntVal(other.day),
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() == to_days_since_epoch(other)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var == other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if self._ymd_consistent and self._ymd_exists and other._ymd_consistent and other._ymd_exists:
                return And(
                    self._year_var == other._year_var,
                    self._month_var == other._month_var,
                    self._day_var == other._day_var,
                )
            # Case 3: Inconsistent - derive epoch expressions for both and compare
            return self._epoch_expr() == other._epoch_expr()
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __add__(self, other) -> 'DateVar':
        """
        DateVar + Period following semantics.
        Steps: normalize Y/M, EOM clamp, then add D days in ordinal space.
        """
        if isinstance(other, Period):
            # Don't add bounds for intermediate results to avoid UNSAT when results go out of range
            result = self.ctx.add_date_var(f"{self.name}_plus", add_bounds=False)
            
            # Fast-path: only days component (check at Python level since Period components are concrete)
            if other.years == 0 and other.months == 0:
                self.ctx.solver.add(result.epoch_var == self._epoch_expr() + IntVal(other.days))
                # Result now has epoch consistent; YMD not yet
                result._epoch_consistent = True
                result._ymd_consistent = False
                return result

            else:
                oy, om, od = (
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
                )

                # Decode current date to Y/M/D
                y0, m0, d0 = self._ymd_expr()

                # Step 1: Combine Y and M with normalization (carry years)
                period_total_months = oy * IntVal(12) + om
                total_months = m0 + period_total_months
                year_carry, m1 = normalize_month(IntVal(0), total_months)
                y1 = y0 + year_carry

                # Step 2: EOM clamp
                d1 = eom_clamp(y1, m1, d0)

                if od == IntVal(0):
                    # No need to re-encode to epoch
                    self.ctx.solver.add(result.year_var == y1)
                    self.ctx.solver.add(result.month_var == m1)
                    self.ctx.solver.add(result.day_var == d1)
                    result._epoch_consistent = False
                    result._ymd_consistent = True
                    return result
                else:
                    # Step 3: add D days in ordinal space
                    self.ctx.solver.add(result.epoch_var == add_days_ordinal(y1, m1, d1, od))
                    result._epoch_consistent = True
                    result._ymd_consistent = False
                    return result
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

    def __init__(self, timeout_ms=600000, use_maxsat=False):
        """Initialize the solver with timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
            use_maxsat: If True, use MaxSAT optimization with soft constraints
        """
        self.use_maxsat = use_maxsat
        if use_maxsat:
            self.solver = Optimize()
        else:
            self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str, add_bounds: bool = True) -> DateVar:
        if name is None:
            name = f"d{len(self.date_vars)}"
        # Ensure uniqueness to avoid collisions when creating multiple temporaries
        base_name = name
        suffix = 0
        while name in self.date_vars:
            suffix += 1
            name = f"{base_name}_{suffix}"
        # Pass is_user_var flag to DateVar constructor
        dv = DateVar(self, name, is_user_var=add_bounds)
        self.date_vars[name] = dv

        # Basic epoch range constraints [1900-03-01 .. 2100-02-28]
        # Only add bounds for user-declared variables, not intermediate arithmetic results
        # to avoid UNSAT when intermediate dates go slightly out of range
        if add_bounds:
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
        """Get concrete dates from the model.
        
        Only returns user-declared variables, filtering out intermediate results
        from arithmetic operations (consistent with other implementations).
        """
        return {
            name: var.to_concrete_date(model)
            for name, var in self.date_vars.items()
            if var._is_user_var
        }

    def solve(self) -> Union[bool, dict]:
        """Solve the constraints."""
        # Add MaxSAT soft constraints if enabled
        if self.use_maxsat:
            from datetime import date
            today = date.today()
            today_days = to_days_since_epoch(Date.from_python_date(today))
            
            # Calculate ±50 years and ±10 years in days (approximate)
            # Using 365.25 days per year for accuracy
            days_50_years = int(50 * 365.25)
            days_10_years = int(10 * 365.25)
            
            # Add soft constraints for each date variable (only user-declared ones)
            for name, date_var in self.date_vars.items():
                if date_var._is_user_var:
                    # Low weight: today ± 50 years
                    within_50_years = And(
                        date_var.epoch_var >= IntVal(today_days - days_50_years),
                        date_var.epoch_var <= IntVal(today_days + days_50_years)
                    )
                    self.solver.add_soft(within_50_years, weight=10)
                    
                    # High weight: today ± 10 years
                    within_10_years = And(
                        date_var.epoch_var >= IntVal(today_days - days_10_years),
                        date_var.epoch_var <= IntVal(today_days + days_10_years)
                    )
                    self.solver.add_soft(within_10_years, weight=100)
        
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
        
        # For user-declared variables, add year bounds consistent with epoch bounds
        # For intermediate results from arithmetic, skip year bounds to avoid UNSAT
        # when intermediate dates go slightly out of range
        if dv._is_user_var:
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
        else:
            # For intermediate results, only add month/day validity constraints
            self.solver.add(
                And(
                    M >= 1,
                    M <= 12,
                    D >= 1,
                    D <= days_in_month(Y, M),
                )
            )
