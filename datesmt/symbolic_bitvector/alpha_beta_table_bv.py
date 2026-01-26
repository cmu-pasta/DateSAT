"""
Alpha-beta-table DATE-SMT using a 4-year (48-month) table.

Representation:
- alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
- beta  (beta_var):  0-based day index within that month (DOM = beta + 1)

We avoid full ordinal decode by using a 48-month DIM/DBM table.
"""

from typing import List, Tuple, Union

from z3 import (
    UGE,
    And,
    BitVec,
    BitVecRef,
    BitVecSort,
    BitVecVal,
    BoolRef,
    CheckSatResult,
    If,
    K,
    ModelRef,
    Not,
    Optimize,
    Or,
    Select,
    Solver,
    Store,
    sat,
    unknown,
    unsat,
)
from ..symbolic_int.alpha_beta_table_int import build_dim_dbm_48_from_epoch
from ..core import Date, Period
from .bitwidths import LEGACY_BITS

# Epoch constants as Python ints for table construction and concrete decoding
_EPOCH_YEAR = 2000
_EPOCH_MONTH = 3
# Linearized epoch month as a Z3 BitVec numeral
_EPOCH_LINEAR = BitVecVal(_EPOCH_YEAR * 12 + _EPOCH_MONTH, LEGACY_BITS)
_FOUR_YEAR_MONTHS = 48
_FOUR_YEAR_DAYS = 1461
# Alpha bounds constants (months since epoch)
_ALPHA_MIN = (1900 - _EPOCH_YEAR) * 12 + (3 - _EPOCH_MONTH)  # -1200
_ALPHA_MAX = (2100 - _EPOCH_YEAR) * 12 + (2 - _EPOCH_MONTH)  # 1199
_DIM48_LIST_PY, _DBM48_LIST_PY = build_dim_dbm_48_from_epoch()


def const_array(values: list[int]) -> BitVecRef:
    a = K(BitVecSort(LEGACY_BITS), BitVecVal(0, LEGACY_BITS))
    for i, v in enumerate(values):
        a = Store(a, BitVecVal(i, LEGACY_BITS), BitVecVal(v, LEGACY_BITS))
    return a


_DIM48_LIST = const_array(_DIM48_LIST_PY)
_DBM48_LIST = const_array(_DBM48_LIST_PY)


def mod48(x) -> BitVecRef:
    return x % BitVecVal(_FOUR_YEAR_MONTHS, LEGACY_BITS)


def _floor_div_12(x) -> BitVecRef:
    """Implement floor division by 12 for bitvectors to match Python's // behavior."""
    sign_bit = 2 ** (LEGACY_BITS - 1)
    wrap_around = 2**LEGACY_BITS
    is_negative = UGE(x, BitVecVal(sign_bit, LEGACY_BITS))
    signed_x = If(is_negative, x - BitVecVal(wrap_around, LEGACY_BITS), x)
    q_trunc = signed_x / BitVecVal(12, LEGACY_BITS)
    r = signed_x % BitVecVal(12, LEGACY_BITS)
    is_negative_and_has_remainder = And(
        UGE(signed_x, BitVecVal(sign_bit, LEGACY_BITS)), r != BitVecVal(0, LEGACY_BITS)
    )
    q = If(is_negative_and_has_remainder, q_trunc - BitVecVal(1, LEGACY_BITS), q_trunc)
    return q


def _floor_div_four_year_days(x) -> BitVecRef:
    """Implement floor division by FOUR_YEAR_DAYS for bitvectors to match Python's // behavior."""
    sign_bit = 2 ** (LEGACY_BITS - 1)
    wrap_around = 2**LEGACY_BITS
    is_negative = UGE(x, BitVecVal(sign_bit, LEGACY_BITS))
    signed_x = If(is_negative, x - BitVecVal(wrap_around, LEGACY_BITS), x)
    q_trunc = signed_x / BitVecVal(_FOUR_YEAR_DAYS, LEGACY_BITS)
    r = signed_x % BitVecVal(_FOUR_YEAR_DAYS, LEGACY_BITS)
    is_negative_and_has_remainder = And(
        UGE(signed_x, BitVecVal(sign_bit, LEGACY_BITS)), r != BitVecVal(0, LEGACY_BITS)
    )
    q = If(is_negative_and_has_remainder, q_trunc - BitVecVal(1, LEGACY_BITS), q_trunc)
    return q


def months_since_epoch_from_ym(y, m) -> BitVecRef:
    return (y * BitVecVal(12, LEGACY_BITS) + m) - _EPOCH_LINEAR


def alpha_to_abs_month(alpha) -> BitVecRef:
    return alpha + _EPOCH_LINEAR


def eom_clamp(dim, beta) -> BitVecRef:
    return If(
        beta < BitVecVal(0, LEGACY_BITS),
        BitVecVal(0, LEGACY_BITS),
        If(
            beta > dim - BitVecVal(1, LEGACY_BITS),
            dim - BitVecVal(1, LEGACY_BITS),
            beta,
        ),
    )


class DateVar:
    """Symbolic date variable using alpha-beta representation.

    alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
    beta  (beta_var):   extra days within that month (0-based), so DOM = 1+beta
    """

    def __init__(self, name: str):
        """Create a symbolic date variable."""
        self.name = name
        # Alpha: Z3 bitvector variable for months since epoch-month
        self.months_var = BitVec(f"{name}_months", LEGACY_BITS)
        # Beta: Z3 bitvector variable for extra days (0-based) within month
        self.beta_var = BitVec(f"{name}_beta", LEGACY_BITS)
        # Solver reference for adding bounds to intermediate dates (set after creation if needed)
        self._solver = None

    def __str__(self) -> str:
        return f"DateVar({self.name})"

    @property
    def year(self) -> BitVecRef:
        """Get symbolic year component (decodes from months_var)."""
        k = self.months_var + _EPOCH_LINEAR
        y = (k - BitVecVal(1, LEGACY_BITS)) / BitVecVal(12, LEGACY_BITS)
        return y

    @property
    def month(self) -> BitVecRef:
        """Get symbolic month component (decodes from months_var)."""
        k = self.months_var + _EPOCH_LINEAR
        y = (k - BitVecVal(1, LEGACY_BITS)) / BitVecVal(12, LEGACY_BITS)
        m = k - y * BitVecVal(12, LEGACY_BITS)
        return m

    @property
    def day(self) -> BitVecRef:
        """Get symbolic day component (beta_var + 1, since beta is 0-based)."""
        return self.beta_var + BitVecVal(1, LEGACY_BITS)

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date using (alpha, beta)."""
        alpha_val = model.evaluate(
            self.months_var, model_completion=True
        ).as_signed_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_signed_long()
        k = alpha_val + (_EPOCH_YEAR * 12 + _EPOCH_MONTH)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        try:
            return Date(year, month, day)
        except ValueError:
            return Date(year, month, day, bounded=False)

    def _add_bounds(self) -> None:
        """Add date validation bounds to this DateVar if solver is available."""
        if self._solver is None:
            return
        
        # Alpha bounds: months since 2000-03
        # 1900-03 => -1200, 2100-02 => 1199
        self._solver.add(self.months_var >= BitVecVal(_ALPHA_MIN, LEGACY_BITS))
        self._solver.add(self.months_var <= BitVecVal(_ALPHA_MAX, LEGACY_BITS))

        # Beta bounds: 0 <= beta < DIM
        idx = mod48(self.months_var)
        dim = Select(_DIM48_LIST, idx)
        self._solver.add(And(self.beta_var >= BitVecVal(0, LEGACY_BITS), self.beta_var < dim))

    def __ge__(self, other) -> BoolRef:
        """Support x >= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)
            return Or(
                self.months_var > alpha_o,
                And(self.months_var == alpha_o, self.beta_var >= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var > other.months_var,
                And(
                    self.months_var == other.months_var, self.beta_var >= other.beta_var
                ),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other) -> BoolRef:
        """Support x <= date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)
            return Or(
                self.months_var < alpha_o,
                And(self.months_var == alpha_o, self.beta_var <= beta_o),
            )
        elif isinstance(other, DateVar):
            return Or(
                self.months_var < other.months_var,
                And(
                    self.months_var == other.months_var, self.beta_var <= other.beta_var
                ),
            )
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
        """Support x == date comparison."""
        if isinstance(other, Date):
            alpha_o = months_since_epoch_from_ym(
                BitVecVal(other.year, LEGACY_BITS), BitVecVal(other.month, LEGACY_BITS)
            )
            beta_o = BitVecVal(other.day - 1, LEGACY_BITS)
            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        elif isinstance(other, DateVar):
            return And(
                self.months_var == other.months_var, self.beta_var == other.beta_var
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other) -> BoolRef:
        """Support x != date comparison using ordinal arithmetic."""
        if isinstance(other, (Date, DateVar)):
            return Not(self.__eq__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __add__(self, other) -> "DateVar":
        result = DateVar(f"{self.name}_plus")

        if isinstance(other, Period):
            months_delta = BitVecVal(other.years * 12 + other.months, LEGACY_BITS)
            days_delta = BitVecVal(other.days, LEGACY_BITS)
        else:
            # Period fields are BitVec terms in our API
            months_delta = other.years * BitVecVal(12, LEGACY_BITS) + other.months
            days_delta = other.days

        # Fast path: days-only period (skip month shift)
        if isinstance(other, Period) and other.years == 0 and other.months == 0:
            # Check if result stays within same month
            alpha1 = self.months_var
            idx1 = mod48(alpha1)
            abs1 = alpha_to_abs_month(alpha1)
            dim1 = Select(_DIM48_LIST, idx1)
            beta1 = eom_clamp(dim1, self.beta_var)

            # Within-month fast path: if beta1 + days_delta stays in [0, dim1)
            new_beta = beta1 + days_delta
            stays_in_month = And(new_beta >= BitVecVal(0, LEGACY_BITS), new_beta < dim1)

            # Within-month: simple addition
            alpha_within = alpha1
            beta_within = new_beta

            # Fallback: use full table lookup (when days cross month boundary)
            base48 = Select(_DBM48_LIST, idx1) + beta1
            total = base48 + days_delta

            q0 = _floor_div_four_year_days(total)
            r0 = total % BitVecVal(_FOUR_YEAR_DAYS, LEGACY_BITS)

            # Compute idx2 by scanning all 48 months with century correction at target
            best = BitVecVal(0, LEGACY_BITS)
            for i in range(1, _FOUR_YEAR_MONTHS):
                dbm_i_corr = Select(_DBM48_LIST, BitVecVal(i, LEGACY_BITS))
                best = If(r0 >= dbm_i_corr, BitVecVal(i, LEGACY_BITS), best)

            idx2 = best
            diff2 = idx2 - idx1
            abs2 = alpha_to_abs_month(alpha1 + q0 * BitVecVal(_FOUR_YEAR_MONTHS, LEGACY_BITS) + diff2)
            beta2 = r0 - (Select(_DBM48_LIST, idx2))

            dim2 = Select(_DIM48_LIST, idx2)
            carry = If(beta2 >= dim2, BitVecVal(1, LEGACY_BITS), BitVecVal(0, LEGACY_BITS))

            alpha_ordinal = alpha1 + q0 * BitVecVal(_FOUR_YEAR_MONTHS, LEGACY_BITS) + diff2 + carry
            beta_ordinal = If(carry == BitVecVal(1, LEGACY_BITS), beta2 - dim2, beta2)

            # Select result based on within-month condition
            result.months_var = If(stays_in_month, alpha_within, alpha_ordinal)
            result.beta_var = If(stays_in_month, beta_within, beta_ordinal)
            # Add bounds to intermediate result
            result._solver = self._solver
            result._add_bounds()
            return result

        # Full path: with month shift
        alpha1 = self.months_var + months_delta
        idx1 = mod48(alpha1)
        abs1 = alpha_to_abs_month(alpha1)
        dim1 = Select(_DIM48_LIST, idx1)
        beta1 = eom_clamp(dim1, self.beta_var)

        # Within-month fast path: if adding days stays in same month
        new_beta = beta1 + days_delta
        stays_in_month = And(new_beta >= BitVecVal(0, LEGACY_BITS), new_beta < dim1)

        # Within-month: simple addition
        alpha_within = alpha1
        beta_within = new_beta

        # Full table lookup path
        base48 = Select(_DBM48_LIST, idx1) + beta1
        total = base48 + days_delta

        q0 = _floor_div_four_year_days(total)
        r0 = total % BitVecVal(_FOUR_YEAR_DAYS, LEGACY_BITS)

        # Compute idx2 by scanning all 48 months with century correction at target
        best = BitVecVal(0, LEGACY_BITS)
        for i in range(1, _FOUR_YEAR_MONTHS):
            dbm_i_corr = Select(_DBM48_LIST, BitVecVal(i, LEGACY_BITS))
            best = If(r0 >= dbm_i_corr, BitVecVal(i, LEGACY_BITS), best)

        idx2 = best
        diff2 = idx2 - idx1
        abs2 = alpha_to_abs_month(alpha1 + q0 * BitVecVal(_FOUR_YEAR_MONTHS, LEGACY_BITS) + diff2)
        beta2 = r0 - (Select(_DBM48_LIST, idx2))

        # End-of-month overflow carry: if beta2 equals/exceeds the month length,
        # advance one month and wrap beta into the next month.
        dim2 = Select(_DIM48_LIST, idx2)
        carry = If(beta2 >= dim2, BitVecVal(1, LEGACY_BITS), BitVecVal(0, LEGACY_BITS))

        alpha_ordinal = alpha1 + q0 * BitVecVal(_FOUR_YEAR_MONTHS, LEGACY_BITS) + diff2 + carry
        beta_ordinal = If(carry == BitVecVal(1, LEGACY_BITS), beta2 - dim2, beta2)

        # Select result based on within-month condition
        result.months_var = If(stays_in_month, alpha_within, alpha_ordinal)
        result.beta_var = If(stays_in_month, beta_within, beta_ordinal)
        # Add bounds to intermediate result
        result._solver = self._solver
        result._add_bounds()
        return result

    def __sub__(self, other) -> "DateVar":
        """DateVar - Period implemented as DateVar + (-Period). Date difference returns Int."""
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class AlphaBetaTableSolver:
    """Alpha-beta date constraint solver using epoch-based conversion."""

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

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        date_var._solver = self.solver
        self.date_vars[name] = date_var

        # Add bounds using _add_bounds method
        date_var._add_bounds()
        return date_var

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
        # Add MaxSAT soft constraints if enabled
        if self.use_maxsat:
            from datetime import date

            today = date.today()
            # Calculate months since epoch for today
            today_months = (today.year - _EPOCH_YEAR) * 12 + (
                today.month - _EPOCH_MONTH
            )

            # Convert years to months
            months_50_years = 50 * 12  # 600 months
            months_10_years = 10 * 12  # 120 months

            # Add soft constraints for each date variable
            for name, date_var in self.date_vars.items():
                # High weight: today ± 50 years
                within_50_years = And(
                    date_var.months_var
                    >= BitVecVal(today_months - months_50_years, LEGACY_BITS),
                    date_var.months_var
                    <= BitVecVal(today_months + months_50_years, LEGACY_BITS),
                )
                self.solver.add_soft(within_50_years, weight=100)

                # Low weight: today ± 10 years
                within_10_years = And(
                    date_var.months_var
                    >= BitVecVal(today_months - months_10_years, LEGACY_BITS),
                    date_var.months_var
                    <= BitVecVal(today_months + months_10_years, LEGACY_BITS),
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
