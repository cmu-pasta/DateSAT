"""
Hybrid DateSAT implementation using dual-lazy representation.

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

from datetime import date, timedelta
from typing import List, Tuple, Union

from z3 import (
    UGE,
    UGT,
    ULE,
    ULT,
    And,
    BitVec,
    BitVecRef,
    BitVecVal,
    BoolRef,
    CheckSatResult,
    ModelRef,
    Not,
    Optimize,
    Or,
    Solver,
    sat,
    unsat,
)
from ..core import Date, Period
from .bitwidths import LEGACY_BITS
from .simple_bv import (
    eom_clamp,
    normalize_month,
    days_in_month
)
from .epoch_days_bv import (
    date_from_days_since_epoch,
    days_since_epoch_from_date,
    add_days_ordinal,
    days_since_epoch_from_ymd,
    ymd_from_days_since_epoch
)

class DateVar:
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str, is_user_var: bool = True):
        """Create a symbolic date variable.
        
        Args:
            ctx: Solver context (HybridSolver instance)
            name: Name of the date variable
            is_user_var: If True, this is a user-declared variable (for filtering in get_concrete_dates)
        """
        self.ctx = ctx
        self.name = name
        # Track if this is a user-declared variable (needs bounds) vs intermediate result
        self._is_user_var = is_user_var
        # Solver reference for adding bounds to intermediate dates
        self._solver = ctx.solver if ctx else None
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
        """Get year component, deriving from epoch if needed."""
        y, _, _ = self._ymd_expr()
        return y

    @property
    def month_var(self) -> BitVecRef:
        """Get month component, deriving from epoch if needed."""
        _, m, _ = self._ymd_expr()
        return m

    @property
    def day_var(self) -> BitVecRef:
        """Get day component, deriving from epoch if needed."""
        _, _, d = self._ymd_expr()
        return d

    # Alias properties for compatibility with parser-generated code
    # The parser generates code like "x.year == y" which expects .year attribute
    @property
    def year(self) -> BitVecRef:
        """Alias for year_var for compatibility with parser-generated code."""
        return self.year_var

    @property
    def month(self) -> BitVecRef:
        """Alias for month_var for compatibility with parser-generated code."""
        return self.month_var

    @property
    def day(self) -> BitVecRef:
        """Alias for day_var for compatibility with parser-generated code."""
        return self.day_var

    def _ensure_ymd(self) -> None:
        """Ensure Y/M/D variables exist. Creates them if they don't exist.
        
        Note: This only creates the vars and links them to epoch. It does NOT
        set consistency flags - that should be done by the caller based on
        which representation is the source of truth.
        """
        if self._ymd_exists:
            return
        self._year_var = BitVec(f"{self.name}_year", LEGACY_BITS)
        self._month_var = BitVec(f"{self.name}_month", LEGACY_BITS)
        self._day_var = BitVec(f"{self.name}_day", LEGACY_BITS)
        self._ymd_exists = True
        # Link YMD to epoch (bidirectional constraint)
        # The epoch bounds (added in add_date_var) ensure Y/M/D stays within valid range
        # Add constraint: epoch_var == days_since_epoch_from_ymd(year_var, month_var, day_var)
        self.ctx.solver.add(
            self.epoch_var
            == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)
        )
        # Note: Consistency flags are NOT set here - caller should set them based on source of truth

    def _epoch_expr(self) -> BitVecRef:
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

    def _ymd_expr(self) -> Tuple[BitVecRef, BitVecRef, BitVecRef]:
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

    def to_concrete_date(self, model: ModelRef) -> Date:
        if self._ymd_consistent and self._ymd_exists:
            y = model.evaluate(self._year_var, model_completion=True).as_signed_long()
            m = model.evaluate(self._month_var, model_completion=True).as_signed_long()
            d = model.evaluate(self._day_var, model_completion=True).as_signed_long()
            try:
                return Date(y, m, d)
            except ValueError:
                # Intermediate result went out of bounds - use unbounded date
                return Date(y, m, d, bounded=False)
        # Otherwise evaluate epoch variable directly 
        # If epoch is consistent, epoch_var is the source of truth
        if self._epoch_consistent:
            e = model.evaluate(self.epoch_var, model_completion=True).as_signed_long()
        else:
            # Epoch not consistent, need to derive from Y/M/D
            e = model.evaluate(self._epoch_expr(), model_completion=True).as_signed_long()
        try:
            return date_from_days_since_epoch(e)
        except ValueError:
            # Epoch out of bounds - convert to Y/M/D then create unbounded date
            from datetime import date, timedelta

            _EPOCH = date(2000, 3, 1)
            result_date = _EPOCH + timedelta(days=e)
            return Date(result_date.year, result_date.month, result_date.day, bounded=False)

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
                y2, m2, d2 = BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS), BitVecVal(other.day, LEGACY_BITS)
                return Or(
                    UGT(y1, y2),
                    And(y1 == y2, Or(UGT(m1, m2), And(m1 == m2, UGE(d1, d2)))),
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() >= BitVecVal(
                days_since_epoch_from_date(other), LEGACY_BITS
            )
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var >= other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if (
                self._ymd_consistent
                and self._ymd_exists
                and other._ymd_consistent
                and other._ymd_exists
            ):
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    UGT(y1, y2),
                    And(y1 == y2, Or(UGT(m1, m2), And(m1 == m2, UGE(d1, d2)))),
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
                y2, m2, d2 = BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS), BitVecVal(other.day, LEGACY_BITS)
                return Or(
                    ULT(y1, y2),
                    And(y1 == y2, Or(ULT(m1, m2), And(m1 == m2, ULE(d1, d2)))),
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() <= BitVecVal(
                days_since_epoch_from_date(other), LEGACY_BITS
            )
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var <= other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if (
                self._ymd_consistent
                and self._ymd_exists
                and other._ymd_consistent
                and other._ymd_exists
            ):
                y1, m1, d1 = self._year_var, self._month_var, self._day_var
                y2, m2, d2 = other._year_var, other._month_var, other._day_var
                return Or(
                    ULT(y1, y2),
                    And(y1 == y2, Or(ULT(m1, m2), And(m1 == m2, ULE(d1, d2)))),
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
                    self._year_var == BitVecVal(other.year, LEGACY_BITS),
                    self._month_var == BitVecVal(other.month, LEGACY_BITS),
                    self._day_var == BitVecVal(other.day, LEGACY_BITS),
                )
            # Otherwise, use epoch comparison
            return self._epoch_expr() == BitVecVal(days_since_epoch_from_date(other), LEGACY_BITS)
        elif isinstance(other, DateVar):
            # Case 1: Both have consistent epoch - use epoch comparison
            if self._epoch_consistent and other._epoch_consistent:
                return self.epoch_var == other.epoch_var
            # Case 2: Both have consistent Y/M/D - use Y/M/D comparison
            if (
                self._ymd_consistent
                and self._ymd_exists
                and other._ymd_consistent
                and other._ymd_exists
            ):
                return And(
                    self._year_var == other._year_var,
                    self._month_var == other._month_var,
                    self._day_var == other._day_var,
                )
            # Case 3: Inconsistent - derive missing representation and compare on common representation
            # If self has epoch consistent, derive other's epoch from Y/M/D and compare on epoch
            if self._epoch_consistent:
                # other must have Y/M/D consistent (otherwise we'd be in Case 1 or 2)
                # Derive other's epoch from its Y/M/D
                other._epoch_expr()  # This will derive epoch and set other._epoch_consistent = True
                # Also derive self's Y/M/D from epoch so both are properly linked
                # This ensures that when self.month is accessed later, it uses Y/M/D derived from epoch
                self._ymd_expr()  # This will derive Y/M/D from epoch and set self._ymd_consistent = True
                return self.epoch_var == other.epoch_var
            # If other has epoch consistent, derive self's epoch from Y/M/D and compare on epoch
            elif other._epoch_consistent:
                # self must have Y/M/D consistent (otherwise we'd be in Case 1 or 2)
                # Derive self's epoch from its Y/M/D
                self._epoch_expr()  # This will derive epoch and set self._epoch_consistent = True
                # Also derive other's Y/M/D from epoch so both are properly linked
                # This ensures that when other.month is accessed later, it uses Y/M/D derived from epoch
                other._ymd_expr()  # This will derive Y/M/D from epoch and set other._ymd_consistent = True
                return self.epoch_var == other.epoch_var
            else:
                # Neither has epoch consistent - both should have Y/M/D consistent (Case 2 should have caught this)
                # But if we get here, derive both epochs and compare
                self._epoch_expr()
                other._epoch_expr()
                return self.epoch_var == other.epoch_var
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def _add_bounds(self) -> None:
        """Add date validation bounds to this DateVar if solver is available."""
        if self._solver is None:
            return
        
        # Prioritize epoch bounds when epoch is consistent (more efficient)
        # Fall back to Y/M/D bounds only if epoch is not consistent but Y/M/D is
        if self._epoch_consistent:
            # Add constraints for valid date ranges [1900-03-01 to 2100-02-28]
            # Epoch is March 1, 2000
            # 1900-03-01 = -36525 days from epoch
            # 2100-02-28 = 36523 days from epoch
            self._solver.add(self.epoch_var >= BitVecVal(-36525, LEGACY_BITS))
            self._solver.add(self.epoch_var <= BitVecVal(36523, LEGACY_BITS))
        elif self._ymd_consistent and self._ymd_exists:
            # Add comprehensive date validation constraints directly to Y/M/D
            # Valid range is 1900-03-01 to 2100-02-28
            self._solver.add(
                Or(
                    # 1900-03-01 to 1900-12-31
                    And(
                        self._year_var == BitVecVal(1900, LEGACY_BITS),
                        self._month_var >= BitVecVal(3, LEGACY_BITS),
                        self._month_var <= BitVecVal(12, LEGACY_BITS),
                        self._day_var >= BitVecVal(1, LEGACY_BITS),
                        self._day_var <= days_in_month(self._year_var, self._month_var),
                    ),
                    # 1901-01-01 to 2099-12-31
                    And(
                        self._year_var >= BitVecVal(1901, LEGACY_BITS),
                        self._year_var <= BitVecVal(2099, LEGACY_BITS),
                        self._month_var >= BitVecVal(1, LEGACY_BITS),
                        self._month_var <= BitVecVal(12, LEGACY_BITS),
                        self._day_var >= BitVecVal(1, LEGACY_BITS),
                        self._day_var <= days_in_month(self._year_var, self._month_var),
                    ),
                    # 2100-01-01 to 2100-02-28
                    And(
                        self._year_var == BitVecVal(2100, LEGACY_BITS),
                        self._month_var >= BitVecVal(1, LEGACY_BITS),
                        self._month_var <= BitVecVal(2, LEGACY_BITS),
                        self._day_var >= BitVecVal(1, LEGACY_BITS),
                        self._day_var <= days_in_month(self._year_var, self._month_var),
                    ),
                )
            )
        else:
            # Neither representation is consistent yet - add bounds to epoch_var as fallback
            # (epoch_var always exists, even if not consistent)
            self._solver.add(self.epoch_var >= BitVecVal(-36525, LEGACY_BITS))
            self._solver.add(self.epoch_var <= BitVecVal(36523, LEGACY_BITS))

    def __add__(self, other) -> "DateVar":
        """Hybrid date + Period: mirror epoch_days semantics, but avoid epoch encode unless days-only.

        - days-only: epoch add (O(1))
        - months/years (and mixed): decode epoch→YMD, normalize months, clamp, add days via ordinal,
          then set result's Y/M/D; epoch derives later when needed.
        """
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to DateVar")

        # Create intermediate result with bounds (following simple/epoch_days pattern)
        # Ensure unique name to avoid collisions
        base_name = f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
        name = base_name
        suffix = 0
        while name in self.ctx.date_vars:
            suffix += 1
            name = f"{base_name}_{suffix}"
        
        # Create DateVar for intermediate result
        result = DateVar(
            self.ctx,
            name,
            is_user_var=False  # Intermediate result, not user-declared
        )
        self.ctx.date_vars[name] = result

        # Fast-path: only days component (check at Python level since Period components are concrete)
        if other.years == 0 and other.months == 0:
            # Direct assignment 
            result.epoch_var = self._epoch_expr() + BitVecVal(other.days, LEGACY_BITS)
            # Result now has epoch consistent; YMD not yet
            result._epoch_consistent = True
            result._ymd_consistent = False
        else:
            oy, om, od = (
                BitVecVal(other.years, LEGACY_BITS),
                BitVecVal(other.months, LEGACY_BITS),
                BitVecVal(other.days, LEGACY_BITS),
            )

            # Decode current date to Y/M/D
            y0, m0, d0 = self._ymd_expr()

            # Step 1: Combine Y and M with normalization (carry years)
            period_total_months = oy * BitVecVal(12, LEGACY_BITS) + om
            total_months = m0 + period_total_months
            year_carry, m1 = normalize_month(BitVecVal(0, LEGACY_BITS), total_months)
            y1 = y0 + year_carry

            # Step 2: EOM clamp
            d1 = eom_clamp(y1, m1, d0)

            if od == BitVecVal(0, LEGACY_BITS):
                # Assign the computed Y/M/D expressions directly
                # (avoiding _ensure_ymd() which would create unused variables and a redundant constraint)
                result._year_var = y1
                result._month_var = m1
                result._day_var = d1
                result._ymd_exists = True
                # Link epoch_var to the Y/M/D values (needed for dual representation consistency)
                # This constraint is essential because:
                # 1. It links epoch_var to the actual Y/M/D values (y1, m1, d1)
                # 2. Without it, epoch_var would be unconstrained, breaking operations that use it
                # 3. It ensures bounds on Y/M/D also constrain epoch_var (via the constraint)
                result.ctx.solver.add(
                    result.epoch_var == days_since_epoch_from_ymd(y1, m1, d1)
                )
                result._epoch_consistent = False
                result._ymd_consistent = True
            else:
                # Direct assignment for epoch_var 
                result.epoch_var = add_days_ordinal(y1, m1, d1, od)
                result._epoch_consistent = True
                result._ymd_consistent = False
            
        # Add bounds to intermediate result
        result._solver = self._solver
        result._add_bounds()
        return result

    def __sub__(self, other) -> "DateVar":
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
        # Create DateVar (always bounded for user variables)
        dv = DateVar(self, name, is_user_var=add_bounds)
        dv._solver = self.solver
        self.date_vars[name] = dv

        # Add bounds using _add_bounds method (following simple/epoch_days pattern)
        dv._add_bounds()
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

            from .epoch_days_bv import days_since_epoch_from_date

            today = date.today()
            today_days = days_since_epoch_from_date(Date.from_python_date(today))

            # Calculate ±50 years and ±10 years in days (approximate)
            # Using 365.25 days per year for accuracy
            days_50_years = int(50 * 365.25)
            days_10_years = int(10 * 365.25)

            # Add soft constraints for each date variable (only user-declared ones)
            for name, date_var in self.date_vars.items():
                if date_var._is_user_var:
                    # High weight: today ± 50 years
                    within_50_years = And(
                        date_var.epoch_var
                        >= BitVecVal(today_days - days_50_years, LEGACY_BITS),
                        date_var.epoch_var
                        <= BitVecVal(today_days + days_50_years, LEGACY_BITS),
                    )
                    self.solver.add_soft(within_50_years, weight=100)

                    # Low weight: today ± 10 years
                    within_10_years = And(
                        date_var.epoch_var
                        >= BitVecVal(today_days - days_10_years, LEGACY_BITS),
                        date_var.epoch_var
                        <= BitVecVal(today_days + days_10_years, LEGACY_BITS),
                    )
                    self.solver.add_soft(within_10_years, weight=10)

        result = self.check()
        if result == sat:
            model = self.model()
            return {
                "status": "sat",
                "dates": self.get_concrete_dates(model),
            }
        elif result == unsat:
            return {"status": "unsat", "dates": {}}
        else:
            # result == unknown (timeout or resource limit)
            return {"status": "timeout", "dates": {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self) -> List[BoolRef]:
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())
