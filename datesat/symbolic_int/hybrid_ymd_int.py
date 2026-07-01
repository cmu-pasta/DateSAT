"""
Hybrid DateSAT implementation using dual-lazy representation — YMD-initial variant.

This module implements a hybrid approach where dates can be represented by
either (Y, M, D) or epoch days, and each side is materialized and kept
consistent lazily on demand. Fresh user variables start with the YMD side as
the source of truth; the epoch side is materialized lazily on first use.

- year/month/day vars: Z3 Ints, valid date components in the bounded window
- epoch_var: Z3 Int, days since 2000-03-01; derived from Y/M/D for free vars

Rules:
- We track which representation is currently consistent via flags.
- A user variable starts with (_epoch_consistent=False, _ymd_consistent=True)
  and an encode linking constraint asserts epoch_var == days_since_epoch_from_ymd(y, m, d).
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
    And,
    ArithRef,
    BoolRef,
    CheckSatResult,
    Int,
    IntVal,
    ModelRef,
    Not,
    Optimize,
    Or,
    Solver,
    sat,
    unsat,
)
from ..core import Date, Period
from .simple_int import (
    normalize_month,
    days_in_month,
    eom_clamp
)
from .epoch_days_int import (
    date_from_days_since_epoch, 
    days_since_epoch_from_date, 
    add_days_ordinal,
    ymd_from_days_since_epoch,
    days_since_epoch_from_ymd
)

class DateVar:
    """Symbolic date variable with lazy dual representation (epoch + Y/M/D)."""

    def __init__(self, ctx, name: str, is_user_var: bool = True):
        """Create a symbolic date variable.

        Args:
            ctx: Solver context (HybridYmdSolver instance)
            name: Name of the date variable
            is_user_var: If True, this is a user-declared variable. User vars are
                eagerly materialized with Y/M/D as the source of truth; intermediate
                results created by __add__ leave the YMD side unmaterialized and let
                __add__ install whichever representation the operation produced.
        """
        self.ctx = ctx
        self.name = name
        # Track if this is a user-declared variable (needs bounds) vs intermediate result
        self._is_user_var = is_user_var
        # Solver reference for adding bounds to intermediate dates
        self._solver = ctx.solver if ctx else None
        # Epoch representation always exists as a Z3 Int (used for cross-encoding linking)
        self.epoch_var = Int(f"{name}_epoch")
        if is_user_var:
            # YMD-initial variant: materialize Y/M/D eagerly as the source of truth
            self._year_var = Int(f"{name}_year")
            self._month_var = Int(f"{name}_month")
            self._day_var = Int(f"{name}_day")
            self._ymd_exists = True
            # Link epoch_var to Y/M/D via the encode formula
            if self._solver is not None:
                self._solver.add(
                    self.epoch_var
                    == days_since_epoch_from_ymd(self._year_var, self._month_var, self._day_var)
                )
            self._epoch_consistent = False
            self._ymd_consistent = True
        else:
            # Intermediate result: __add__ will install the appropriate representation
            self._ymd_exists = False
            self._year_var = None
            self._month_var = None
            self._day_var = None
            self._epoch_consistent = True
            self._ymd_consistent = False

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    # Back-compat property name used in some places
    @property
    def days_var(self) -> ArithRef:
        return self.epoch_var

    @property
    def year_var(self) -> ArithRef:
        """Get year component, deriving from epoch if needed."""
        y, _, _ = self._ymd_expr()
        return y

    @property
    def month_var(self) -> ArithRef:
        """Get month component, deriving from epoch if needed."""
        _, m, _ = self._ymd_expr()
        return m

    @property
    def day_var(self) -> ArithRef:
        """Get day component, deriving from epoch if needed."""
        _, _, d = self._ymd_expr()
        return d

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
        # Otherwise evaluate epoch variable directly 
        # If epoch is consistent, epoch_var is the source of truth
        if self._epoch_consistent:
            e = model.evaluate(self.epoch_var, model_completion=True).as_long()
        else:
            # Epoch not consistent, need to derive from Y/M/D
            e = model.evaluate(self._epoch_expr(), model_completion=True).as_long()
        try:
            return date_from_days_since_epoch(e)
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
        # Link YMD to epoch (bidirectional constraint)
        # The epoch bounds (added in add_date_var) ensure Y/M/D stays within valid range
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
            return self._epoch_expr() >= days_since_epoch_from_date(other)
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
            return self._epoch_expr() <= days_since_epoch_from_date(other)
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
            return self._epoch_expr() == days_since_epoch_from_date(other)
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

        # Year range bound removed - any year is allowed as long as the date is valid.
        # Epoch representation is naturally well-formed (any integer is a valid days-since-epoch);
        # Y/M/D representation needs explicit well-formedness constraints.
        # Previous range was 1900-03-01 to 2100-02-28:
        # if self._epoch_consistent:
        #     self._solver.add(self.epoch_var >= IntVal(-36525))
        #     self._solver.add(self.epoch_var <= IntVal(36523))
        # elif self._ymd_consistent and self._ymd_exists:
        #     self._solver.add(
        #         Or(
        #             And(
        #                 self._year_var == 1900,
        #                 self._month_var >= 3,
        #                 self._month_var <= 12,
        #                 self._day_var >= 1,
        #                 self._day_var <= days_in_month(self._year_var, self._month_var),
        #             ),
        #             And(
        #                 self._year_var >= 1901,
        #                 self._year_var <= 2099,
        #                 self._month_var >= 1,
        #                 self._month_var <= 12,
        #                 self._day_var >= 1,
        #                 self._day_var <= days_in_month(self._year_var, self._month_var),
        #             ),
        #             And(
        #                 self._year_var == 2100,
        #                 self._month_var >= 1,
        #                 self._month_var <= 2,
        #                 self._day_var >= 1,
        #                 self._day_var <= days_in_month(self._year_var, self._month_var),
        #             ),
        #         )
        #     )
        # else:
        #     self._solver.add(self.epoch_var >= IntVal(-36525))
        #     self._solver.add(self.epoch_var <= IntVal(36523))

        # Well-formedness: when Y/M/D vars are the source of truth, they're free Z3
        # integers and the encoding formula (epoch = days_since_epoch_from_ymd(y,m,d))
        # doesn't force well-formedness on Y/M/D - the solver could pick m=17, d=100.
        # So we constrain m in [1,12] and d in [1, days_in_month(y,m)] here.
        # When epoch is source of truth, Y/M/D are either absent or asserted from the
        # decoding formula (which always produces valid Y/M/D), so no constraint needed.
        if self._ymd_consistent and self._ymd_exists:
            self._solver.add(
                And(
                    self._month_var >= 1,
                    self._month_var <= 12,
                    self._day_var >= 1,
                    self._day_var <= days_in_month(self._year_var, self._month_var),
                )
            )

    def __add__(self, other) -> 'DateVar':
        """
        DateVar + Period following semantics.
        Steps: normalize Y/M, EOM clamp, then add D days in ordinal space.
        """
        if isinstance(other, Period):
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
                result.epoch_var = self._epoch_expr() + IntVal(other.days)
                # Result now has epoch consistent; YMD not yet
                result._epoch_consistent = True
                result._ymd_consistent = False
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
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other) -> "DateVar":
        """DateVar - Period implemented as DateVar + (-Period)."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class HybridYmdSolver:
    """Hybrid date constraint solver using dual representation, YMD-initial variant.

    Fresh DateVars start in YMD-only state: Y/M/D vars are materialized upfront and
    asserted as a valid bounded date; epoch_var is linked via the encode formula
    and treated as derived. Operations may flip the source of truth to epoch when
    appropriate (day-only addition, comparisons that benefit from it).
    """

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
                        date_var.epoch_var >= IntVal(today_days - days_50_years),
                        date_var.epoch_var <= IntVal(today_days + days_50_years),
                    )
                    self.solver.add_soft(within_50_years, weight=100)

                    # Low weight: today ± 10 years
                    within_10_years = And(
                        date_var.epoch_var >= IntVal(today_days - days_10_years),
                        date_var.epoch_var <= IntVal(today_days + days_10_years),
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

