"""
Alpha-beta DATE-SMT using a 4-year (48-month) table with century corrections.

Representation:
- alpha (months_var): months since epoch month 2000-03 (March 2000 = 0)
- beta  (beta_var):  0-based day index within that month (DOM = beta + 1)

We avoid full ordinal decode by using a 48-month DIM/DBM table, plus
step-function corrections for the non-leap centuries (1900-02, 2100-02).
"""

from z3 import (
    And,
    BoolRef,
    CheckSatResult,
    If,
    Int,
    IntSort,
    IntVal,
    K,
    ModelRef,
    Not,
    Or,
    Select,
    Store,
    Solver,
    sat,
)

from .core import Date, Period

EPOCH_YEAR = 2000
EPOCH_MONTH = 3
E_LINEAR = IntVal(EPOCH_YEAR * 12 + EPOCH_MONTH)

FOUR_YEAR_MONTHS = 48
FOUR_YEAR_DAYS = 1461

T1900_FEB = IntVal(1900 * 12 + 2)
T1900_MAR = IntVal(1900 * 12 + 3)
T2100_FEB = IntVal(2100 * 12 + 2)
T2100_MAR = IntVal(2100 * 12 + 3)


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
    a = K(IntSort(), IntVal(0))
    for i, v in enumerate(values):
        a = Store(a, IntVal(i), IntVal(v))
    return a


DIM48_ARR = _const_array(_DIM48_LIST)
DBM48_ARR = _const_array(_DBM48_LIST)


def _mod48(x):
    return x % IntVal(FOUR_YEAR_MONTHS)


def _alpha_to_abs_month(alpha):
    return alpha + E_LINEAR


def _months_since_epoch_from_ym(y, m):
    return (y * IntVal(12) + m) - E_LINEAR


def _ym_from_months_since_epoch(alpha):
    k = alpha + E_LINEAR
    y = (k - IntVal(1)) / IntVal(12)
    m = k - y * IntVal(12)
    return y, m


def _century_correction(abs_month):
    # +1 if before 1900-03, -1 if at/after 2100-03, else 0
    return If(
        abs_month < T1900_MAR,
        IntVal(1),
        If(abs_month >= T2100_MAR, IntVal(-1), IntVal(0)),
    )


def _override_dim_for_century_feb(abs_month, dim):
    return If(Or(abs_month == T1900_FEB, abs_month == T2100_FEB), IntVal(28), dim)


def _eom_clamp(dim, beta):
    return If(beta < IntVal(0), IntVal(0), If(beta > dim - IntVal(1), dim - IntVal(1), beta))


class DateVar:
    def __init__(self, name: str):
        self.name = name
        self.months_var = Int(f"{name}_months")
        self.beta_var = Int(f"{name}_beta")

    def __str__(self):
        return f"DateVar({self.name})"

    def __repr__(self):
        return self.__str__()

    def to_concrete_date(self, model: ModelRef) -> Date:
        alpha_val = model.evaluate(self.months_var, model_completion=True).as_long()
        beta_val = model.evaluate(self.beta_var, model_completion=True).as_long()
        k = alpha_val + (EPOCH_YEAR * 12 + EPOCH_MONTH)
        year = (k - 1) // 12
        month = k - year * 12
        day = beta_val + 1
        return Date(year, month, day)

    # Lexicographic comparisons on (alpha, beta)
    def __ge__(self, other):
        if isinstance(other, Date):
            alpha_o = _months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
            return Or(self.months_var > alpha_o, And(self.months_var == alpha_o, self.beta_var >= beta_o))
        elif isinstance(other, DateVar):
            return Or(self.months_var > other.months_var, And(self.months_var == other.months_var, self.beta_var >= other.beta_var))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __le__(self, other):
        if isinstance(other, Date):
            alpha_o = _months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
            return Or(self.months_var < alpha_o, And(self.months_var == alpha_o, self.beta_var <= beta_o))
        elif isinstance(other, DateVar):
            return Or(self.months_var < other.months_var, And(self.months_var == other.months_var, self.beta_var <= other.beta_var))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __lt__(self, other):
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__ge__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __gt__(self, other):
        if isinstance(other, Date) or isinstance(other, DateVar):
            return Not(self.__le__(other))
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __eq__(self, other):
        if isinstance(other, Date):
            alpha_o = _months_since_epoch_from_ym(IntVal(other.year), IntVal(other.month))
            beta_o = IntVal(other.day - 1)
            return And(self.months_var == alpha_o, self.beta_var == beta_o)
        elif isinstance(other, DateVar):
            return And(self.months_var == other.months_var, self.beta_var == other.beta_var)
        else:
            raise TypeError(f"Cannot compare DateVar with {type(other)}")

    def __ne__(self, other):
        return Not(self.__eq__(other))

    def __add__(self, other):
        if not (isinstance(other, Period) or isinstance(other, PeriodVar)):
            raise TypeError(f"Cannot add {type(other)} to DateVar")

        result = DateVar(f"{self.name}_plus")
    
        if isinstance(other, Period):
            months_delta = IntVal(other.years * 12 + other.months)
            days_delta = IntVal(other.days)
        else:
            months_delta = other.years * IntVal(12) + other.months
            days_delta = other.days

        alpha1 = self.months_var + months_delta
        idx1 = _mod48(alpha1)
        abs1 = _alpha_to_abs_month(alpha1)
        dim1 = _override_dim_for_century_feb(abs1, Select(DIM48_ARR, idx1))
        beta1 = _eom_clamp(dim1, self.beta_var)

        base48 = Select(DBM48_ARR, idx1) + beta1
        corr1 = _century_correction(abs1)
        total = base48 + corr1 + days_delta

        q0 = total / IntVal(FOUR_YEAR_DAYS)
        r0 = total % IntVal(FOUR_YEAR_DAYS)

        def scan_idx(r_expr):
            i = IntVal(0)
            for k in range(1, FOUR_YEAR_MONTHS):
                i = If(r_expr >= IntVal(_DBM48_LIST[k]), IntVal(k), i)
            return i

        # Compute idx2 by scanning all 48 months with century correction at target
        best = IntVal(0)
        for i in range(1, FOUR_YEAR_MONTHS):
            diff_i = IntVal(i) - idx1
            abs_i = _alpha_to_abs_month(alpha1 + q0 * IntVal(FOUR_YEAR_MONTHS) + diff_i)
            corr_i = _century_correction(abs_i)
            dbm_i_corr = Select(DBM48_ARR, IntVal(i)) + corr_i
            best = If(r0 >= dbm_i_corr, IntVal(i), best)

        idx2 = best
        diff2 = idx2 - idx1
        abs2 = _alpha_to_abs_month(alpha1 + q0 * IntVal(FOUR_YEAR_MONTHS) + diff2)
        corr2 = _century_correction(abs2)
        beta2 = r0 - (Select(DBM48_ARR, idx2) + corr2)

        # End-of-month overflow carry: if beta2 equals/exceeds the (possibly overridden)
        # month length, advance one month and wrap beta into the next month.
        dim2 = _override_dim_for_century_feb(abs2, Select(DIM48_ARR, idx2))
        carry = If(beta2 >= dim2, IntVal(1), IntVal(0))

        result.months_var = alpha1 + q0 * IntVal(FOUR_YEAR_MONTHS) + diff2 + carry
        result.beta_var = If(carry == IntVal(1), beta2 - dim2, beta2)
        return result

    def __radd__(self, other):
        if isinstance(other, Period) or isinstance(other, PeriodVar):
            return self.__add__(other)
        else:
            raise TypeError(f"Cannot add {type(other)} to DateVar")

    def __sub__(self, other):
        if isinstance(other, Period):
            neg = Period(-other.years, -other.months, -other.days)
            return self.__add__(neg)
        elif isinstance(other, PeriodVar):
            neg = PeriodVar(f"neg_{getattr(other, 'name', 'p')}")
            neg.years = -other.years
            neg.months = -other.months
            neg.days = -other.days
            return self.__add__(neg)
        else:
            raise TypeError(f"Cannot subtract {type(other)} from DateVar")

    def diff_days(self, other) -> Int:
        # Compute days since epoch using 48-month base + correction
        idx = _mod48(self.months_var)
        q = (self.months_var - idx) / IntVal(FOUR_YEAR_MONTHS)
        absm = _alpha_to_abs_month(self.months_var)
        days_self = q * IntVal(FOUR_YEAR_DAYS) + Select(DBM48_ARR, idx) + _century_correction(absm) + self.beta_var

        if isinstance(other, DateVar):
            idx_o = _mod48(other.months_var)
            q_o = (other.months_var - idx_o) / IntVal(FOUR_YEAR_MONTHS)
            absm_o = _alpha_to_abs_month(other.months_var)
            days_o = q_o * IntVal(FOUR_YEAR_DAYS) + Select(DBM48_ARR, idx_o) + _century_correction(absm_o) + other.beta_var
            return days_self - days_o
        elif isinstance(other, Date):
            alpha_o = (IntVal(other.year) * IntVal(12) + IntVal(other.month)) - E_LINEAR
            idx_o = _mod48(alpha_o)
            q_o = (alpha_o - idx_o) / IntVal(FOUR_YEAR_MONTHS)
            absm_o = _alpha_to_abs_month(alpha_o)
            beta_o = IntVal(other.day - 1)
            days_o = q_o * IntVal(FOUR_YEAR_DAYS) + Select(DBM48_ARR, idx_o) + _century_correction(absm_o) + beta_o
            return days_self - days_o
        else:
            raise TypeError("diff_days expects DateVar or Date")


class PeriodVar:
    """Symbolic period variable using separate Y/M/D components (baseline-compatible)."""

    def __init__(self, name: str, years=0, months=0, days=0):
        self.name = name
        self.years = Int(f"{name}_years")
        self.months = Int(f"{name}_months")
        self.days = Int(f"{name}_days")

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
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
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
                    IntVal(other.years),
                    IntVal(other.months),
                    IntVal(other.days),
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


class AbNewDateSolver:
    def __init__(self, timeout_ms=60000):
        self.solver = Solver()
        self.solver.set("timeout", timeout_ms)
        self.date_vars = {}
        self.period_vars = {}
        self.constraints = []
        self.timeout_ms = timeout_ms

    def add_date_var(self, name: str) -> DateVar:
        dv = DateVar(name)
        self.date_vars[name] = dv
        # Bounds [1900-01 .. 2100-12]
        self.solver.add(dv.months_var >= IntVal((1900 - EPOCH_YEAR) * 12 + (1 - EPOCH_MONTH)))
        self.solver.add(dv.months_var <= IntVal((2100 - EPOCH_YEAR) * 12 + (12 - EPOCH_MONTH)))

        # Beta bounds: 0 <= beta < DIM (with century Feb override)
        idx = _mod48(dv.months_var)
        absm = _alpha_to_abs_month(dv.months_var)
        dim = _override_dim_for_century_feb(absm, Select(DIM48_ARR, idx))
        self.solver.add(And(dv.beta_var >= IntVal(0), dv.beta_var < dim))
        return dv

    def add_period_var(self, name: str) -> PeriodVar:
        pv = PeriodVar(name)
        self.period_vars[name] = pv
        return pv

    def add_constraint(self, constraint: BoolRef):
        self.constraints.append(constraint)
        self.solver.add(constraint)

    def check(self) -> CheckSatResult:
        return self.solver.check()

    def model(self) -> ModelRef:
        return self.solver.model()

    def get_concrete_dates(self, model: ModelRef) -> dict:
        return {name: var.to_concrete_date(model) for name, var in self.date_vars.items()}

    def get_concrete_periods(self, model: ModelRef) -> dict:
        return {name: var.to_concrete_period(model) for name, var in self.period_vars.items()}

    def solve(self):
        res = self.check()
        if res == sat:
            m = self.model()
            return {
                'status': 'sat',
                'dates': self.get_concrete_dates(m),
                'periods': self.get_concrete_periods(m),
            }
        else:
            return {'status': 'unsat', 'dates': {}, 'periods': {}}

    def to_smt2(self) -> str:
        return self.solver.to_smt2()

    def get_assertions(self):
        return list(self.solver.assertions())


