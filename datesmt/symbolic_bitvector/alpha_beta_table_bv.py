"""
Alpha-beta-table DATE-SMT using a 4-year (48-month) table with century corrections.

Representation:
- alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
- beta  (beta_var):  0-based day index within that month (DOM = beta + 1)

We avoid full ordinal decode by using a 48-month DIM/DBM table, plus
step-function corrections for the non-leap centuries (1900-02, 2100-02).
"""

from typing import Union

from z3 import (
    UGE,
    ULT,
    And,
    BitVec,
    BitVecSort,
    BitVecVal,
    BoolRef,
    CheckSatResult,
    If,
    K,
    ModelRef,
    Not,
    Or,
    Select,
    Solver,
    Store,
    sat,
    unsat,
)

from ..core import Date, Period

# Epoch constants as Python ints for table construction and concrete decoding
EPOCH_YEAR = 2000
EPOCH_MONTH = 3
# Linearized epoch month as a Z3 Int numeral
_EPOCH_LINEAR = BitVecVal(EPOCH_YEAR * 12 + EPOCH_MONTH, 32)

FOUR_YEAR_MONTHS = 48
FOUR_YEAR_DAYS = 1461

T1900_FEB = BitVecVal(1900 * 12 + 2, 32)
T1900_MAR = BitVecVal(1900 * 12 + 3, 32)
T2100_FEB = BitVecVal(2100 * 12 + 2, 32)
T2100_MAR = BitVecVal(2100 * 12 + 3, 32)


def _is_leap_py(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def _days_in_month_py(y: int, m: int) -> int:
    if m == 2:
        return 29 if _is_leap_py(y) else 28
    if m in (4, 6, 9, 11):
        return 30
    return 31


def _add_months(y: int, m: int, delta: int) -> tuple[int, int]:
    total = (y * 12 + m) + delta
    y2 = (total - 1) // 12
    m2 = total - y2 * 12
    return y2, m2


def _build_dim_dbm_48_from_epoch() -> tuple[list[int], list[int]]:
    dim: list[int] = [0] * FOUR_YEAR_MONTHS
    dbm: list[int] = [0] * FOUR_YEAR_MONTHS
    y, m = EPOCH_YEAR, EPOCH_MONTH
    cum = 0
    for i in range(FOUR_YEAR_MONTHS):
        dbm[i] = cum
        d = _days_in_month_py(y, m)
        dim[i] = d
        cum += d
        y, m = _add_months(y, m, 1)
    assert cum == FOUR_YEAR_DAYS
    return dim, dbm


_DIM48_LIST, _DBM48_LIST = _build_dim_dbm_48_from_epoch()


def _const_array(values: list[int]):
    a = K(BitVecSort(32), BitVecVal(0, 32))
    for i, v in enumerate(values):
        a = Store(a, BitVecVal(i, 32), BitVecVal(v, 32))
    return a


DIM48_ARR = _const_array(_DIM48_LIST)
DBM48_ARR = _const_array(_DBM48_LIST)


def _mod48(x):
    return x % BitVecVal(FOUR_YEAR_MONTHS, 32)


def _floor_div_12(x):
    """Implement floor division by 12 for bitvectors to match Python's // behavior."""
    # Check if x is negative (>= 2^31)
    is_negative = UGE(x, BitVecVal(2**31, 32))

    # Convert to signed value if negative
    signed_x = If(is_negative, x - BitVecVal(2**32, 32), x)

    # Implement floor division: if x < 0 and x % 12 != 0, subtract 1 from quotient
    q_trunc = signed_x / BitVecVal(12, 32)  # Truncating division
    r = signed_x % BitVecVal(12, 32)  # Modulo
    is_negative_and_has_remainder = And(
        UGE(signed_x, BitVecVal(2**31, 32)), r != BitVecVal(0, 32)
    )
    q = If(is_negative_and_has_remainder, q_trunc - BitVecVal(1, 32), q_trunc)

    return q


def _floor_div_four_year_days(x):
    """Implement floor division by FOUR_YEAR_DAYS for bitvectors to match Python's // behavior."""
    # Check if x is negative (>= 2^31)
    is_negative = UGE(x, BitVecVal(2**31, 32))

    # Convert to signed value if negative
    signed_x = If(is_negative, x - BitVecVal(2**32, 32), x)

    # Implement floor division: if x < 0 and x % FOUR_YEAR_DAYS != 0, subtract 1 from quotient
    q_trunc = signed_x / BitVecVal(FOUR_YEAR_DAYS, 32)  # Truncating division
    r = signed_x % BitVecVal(FOUR_YEAR_DAYS, 32)  # Modulo
    is_negative_and_has_remainder = And(
        UGE(signed_x, BitVecVal(2**31, 32)), r != BitVecVal(0, 32)
    )
    q = If(is_negative_and_has_remainder, q_trunc - BitVecVal(1, 32), q_trunc)

    return q


def _alpha_to_abs_month(alpha):
    return alpha + _EPOCH_LINEAR


def _months_since_epoch_from_ym(y, m):
    return (y * BitVecVal(12, 32) + m) - _EPOCH_LINEAR


def _century_correction(abs_month):
    # +1 if before 1900-03, -1 if at/after 2100-03, else 0
    return If(
        abs_month < T1900_MAR,
        BitVecVal(1, 32),
        If(abs_month >= T2100_MAR, BitVecVal(-1, 32), BitVecVal(0, 32)),
    )


def _override_dim_for_century_feb(abs_month, dim):
    return If(
        Or(abs_month == T1900_FEB, abs_month == T2100_FEB), BitVecVal(28, 32), dim
    )


def _eom_clamp(dim, beta):
    return If(
        beta < BitVecVal(0, 32),
        BitVecVal(0, 32),
        If(beta > dim - BitVecVal(1, 32), dim - BitVecVal(1, 32), beta),
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
        self.months_var = BitVec(f"{name}_months", 32)
        # Beta: Z3 bitvector variable for extra days (0-based) within month
        self.beta_var = BitVec(f"{name}_beta", 32)

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    @property
    def year(self):
        """Convert months_var to year component."""
        k = self.months_var + (EPOCH_YEAR * 12 + EPOCH_MONTH)
        return _floor_div_12(k - 1)

    @property
    def month(self):
        """Convert months_var to month component."""
        k = self.months_var + (EPOCH_YEAR * 12 + EPOCH_MONTH)
        year = _floor_div_12(k - 1)
        return k - year * 12

    @property
    def day(self):
        """Convert beta_var to day component."""
        return self.beta_var + 1

    def to_concrete_date(self, model: ModelRef) -> Date:
        """Convert Z3 model to concrete Date using (alpha, beta)."""
        alpha_val = model.evaluate(
            self.months_var, model_completion=True
        ).as_signed_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_long()
        k = alpha_val + (EPOCH_YEAR * 12 + EPOCH_MONTH)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        return Date(year, month, day)

    def __ge__(self, other):
        """Support x >= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to bitvector values if needed
            if isinstance(other, Date):
                alpha_o = _months_since_epoch_from_ym(
                    BitVecVal(other.year, 32), BitVecVal(other.month, 32)
                )
                beta_o = BitVecVal(other.day - 1, 32)
            else:  # isinstance(other, DateVar)
                alpha_o = other.months_var
                beta_o = other.beta_var

            return Or(
                self.months_var > alpha_o,
                And(self.months_var == alpha_o, self.beta_var >= beta_o),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        """Support x <= date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to bitvector values if needed
            if isinstance(other, Date):
                alpha_o = _months_since_epoch_from_ym(
                    BitVecVal(other.year, 32), BitVecVal(other.month, 32)
                )
                beta_o = BitVecVal(other.day - 1, 32)
            else:  # isinstance(other, DateVar)
                alpha_o = other.months_var
                beta_o = other.beta_var

            return Or(
                self.months_var < alpha_o,
                And(self.months_var == alpha_o, self.beta_var <= beta_o),
            )
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other):
        """Support x < date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other):
        """Support x > date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        """Support x == date comparison."""
        if isinstance(other, Date) or isinstance(other, DateVar):
            # Convert Date to bitvector values if needed
            if isinstance(other, Date):
                alpha_o = _months_since_epoch_from_ym(
                    BitVecVal(other.year, 32), BitVecVal(other.month, 32)
                )
                beta_o = BitVecVal(other.day - 1, 32)
            else:  # isinstance(other, DateVar)
                alpha_o = other.months_var
                beta_o = other.beta_var

            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        """Support x != date comparison."""
        return Not(self.__eq__(other))

    def __add__(self, other):
        if not (isinstance(other, Period) or isinstance(other, PeriodVar)):
            raise TypeError(f"Cannot add {type(other)} to DateVar")

        result = DateVar(f"{self.name}_plus")

        if (
            hasattr(other, 'years')
            and hasattr(other, 'months')
            and hasattr(other, 'days')
            and not isinstance(other, PeriodVar)
        ):
            months_delta = BitVecVal(other.years * 12 + other.months, 32)
            days_delta = BitVecVal(other.days, 32)
        else:
            months_delta = other.years * BitVecVal(12, 32) + other.months
            days_delta = other.days

        alpha1 = self.months_var + months_delta
        idx1 = _mod48(alpha1)
        abs1 = _alpha_to_abs_month(alpha1)
        dim1 = _override_dim_for_century_feb(abs1, Select(DIM48_ARR, idx1))
        beta1 = _eom_clamp(dim1, self.beta_var)

        base48 = Select(DBM48_ARR, idx1) + beta1
        corr1 = _century_correction(abs1)
        total = base48 + corr1 + days_delta

        q0 = _floor_div_four_year_days(total)
        r0 = total % BitVecVal(FOUR_YEAR_DAYS, 32)

        def scan_idx(r_expr):
            i = BitVecVal(0, 32)
            for k in range(1, FOUR_YEAR_MONTHS):
                i = If(r_expr >= BitVecVal(_DBM48_LIST[k]), BitVecVal(k), i)
            return i

        # Compute idx2 by scanning all 48 months with century correction at target
        best = BitVecVal(0, 32)
        for i in range(1, FOUR_YEAR_MONTHS):
            diff_i = BitVecVal(i, 32) - idx1
            abs_i = _alpha_to_abs_month(
                alpha1 + q0 * BitVecVal(FOUR_YEAR_MONTHS, 32) + diff_i
            )
            corr_i = _century_correction(abs_i)
            dbm_i_corr = Select(DBM48_ARR, BitVecVal(i, 32)) + corr_i
            best = If(r0 >= dbm_i_corr, BitVecVal(i, 32), best)

        idx2 = best
        diff2 = idx2 - idx1
        abs2 = _alpha_to_abs_month(
            alpha1 + q0 * BitVecVal(FOUR_YEAR_MONTHS, 32) + diff2
        )
        corr2 = _century_correction(abs2)
        beta2 = r0 - (Select(DBM48_ARR, idx2) + corr2)

        # End-of-month overflow carry: if beta2 equals/exceeds the (possibly overridden)
        # month length, advance one month and wrap beta into the next month.
        dim2 = _override_dim_for_century_feb(abs2, Select(DIM48_ARR, idx2))
        carry = If(beta2 >= dim2, BitVecVal(1, 32), BitVecVal(0, 32))

        result.months_var = (
            alpha1 + q0 * BitVecVal(FOUR_YEAR_MONTHS, 32) + diff2 + carry
        )
        result.beta_var = If(carry == BitVecVal(1, 32), beta2 - dim2, beta2)
        return result

    def __radd__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            return self.__add__(other)
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other):
        """DateVar - Period implemented as DateVar + (-Period). Date difference returns Int."""
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                neg = Period(-other.years, -other.months, -other.days)
            else:
                neg = PeriodVar(f"neg_{other.name}")
                neg.years = -other.years
                neg.months = -other.months
                neg.days = -other.days
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")


class PeriodVar:
    """Symbolic period variable using separate Y/M/D components (baseline-compatible)."""

    def __init__(self, name: str, years=0, months=0, days=0):
        self.name = name
        self.years = BitVec(f"{name}_years", 32)
        self.months = BitVec(f"{name}_months", 32)
        self.days = BitVec(f"{name}_days", 32)

    def __str__(self):
        return f"PeriodVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_period(self, model: ModelRef) -> Period:
        years = model.evaluate(self.years, model_completion=True).as_long()
        months = model.evaluate(self.months, model_completion=True).as_long()
        days = model.evaluate(self.days, model_completion=True).as_long()
        return Period(years, months, days)

    def __eq__(self, other):
        raise TypeError(f"Cannot compare PeriodVar.")

    def __ne__(self, other):
        raise TypeError(f"Cannot compare PeriodVar.")

    def __add__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                result = PeriodVar(
                    f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
                )
                oy, om, od = (
                    BitVecVal(other.years, 32),
                    BitVecVal(other.months, 32),
                    BitVecVal(other.days, 32),
                )
                result.years = self.years + oy
                result.months = self.months + om
                result.days = self.days + od
            else:
                result = PeriodVar(f"{self.name}_plus_{other.name}")
                result.years = self.years + other.years
                result.months = self.months + other.months
                result.days = self.days + other.days
            return result
        else:
            raise TypeError(f"Cannot add {type(other)} to PeriodVar")

    def __sub__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            if isinstance(other, Period):
                result = PeriodVar(
                    f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d"
                )
                oy, om, od = (
                    BitVecVal(other.years, 32),
                    BitVecVal(other.months, 32),
                    BitVecVal(other.days, 32),
                )
                result.years = self.years - oy
                result.months = self.months - om
                result.days = self.days - od
            else:
                result = PeriodVar(f"{self.name}_minus_{other.name}")
                result.years = self.years - other.years
                result.months = self.months - other.months
                result.days = self.days - other.days
            return result
        else:
            raise TypeError(f"Cannot subtract {type(other)} from PeriodVar")


class AlphaBetaTableSolver:
    """Alpha-beta date constraint solver using epoch-based conversion."""

    def __init__(self, timeout_ms=60000):
        """Initialize the solver with timeout.

        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        """Add a symbolic date variable with basic constraints."""
        date_var = DateVar(name)
        self.date_vars[name] = date_var

        # Alpha bounds: months since 2000-03
        # 1900-03 => (1900-2000)*12 + (3-3)
        # 2100-02 => (2100-2000)*12 + (2-3)
        self.solver.add(
            date_var.months_var
            >= BitVecVal((1900 - EPOCH_YEAR) * 12 + (3 - EPOCH_MONTH), 32)
        )
        self.solver.add(
            date_var.months_var
            <= BitVecVal((2100 - EPOCH_YEAR) * 12 + (2 - EPOCH_MONTH), 32)
        )

        # Beta bounds: 0 <= beta < DIM (with century Feb override)
        idx = _mod48(date_var.months_var)
        absm = _alpha_to_abs_month(date_var.months_var)
        dim = _override_dim_for_century_feb(absm, Select(DIM48_ARR, idx))
        self.solver.add(
            And(date_var.beta_var >= BitVecVal(0, 32), date_var.beta_var < dim)
        )
        return date_var

    def add_period_var(self, name: str) -> PeriodVar:
        """Add a symbolic period variable."""
        period_var = PeriodVar(name)
        self.period_vars[name] = period_var
        return period_var

    def add_constraint(self, constraint: BoolRef):
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

    def get_concrete_periods(self, model: ModelRef) -> dict:
        """Get concrete periods from the model."""
        return {
            name: var.to_concrete_period(model)
            for name, var in self.period_vars.items()
        }

    def solve(self) -> Union[bool, dict]:
        """Solve the constraints."""
        result = self.check()
        if result == sat:
            model = self.model()
            return {
                'status': 'sat',
                'dates': self.get_concrete_dates(model),
                'periods': self.get_concrete_periods(model),
            }
        else:
            return {'status': 'unsat', 'dates': {}, 'periods': {}}

    def to_smt2(self) -> str:
        """Return the current problem in SMT-LIB v2 format."""
        return self.solver.to_smt2()

    def get_assertions(self):
        """Return the list of current Z3 assertions (BoolRef)."""
        return list(self.solver.assertions())
