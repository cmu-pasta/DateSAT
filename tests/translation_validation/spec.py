"""
Z3 transcription of the Verus reference semantics in proofs/src/.

Every function here is copied line by line from a Verus `spec fn` and is named
after it. Verus `/` and `%` on `int` are Euclidean, the same as Z3's Int
`/` and `%`, so the transcription is literal. Nothing in this file imports
from `datesat`, so the checks never compare the implementation with itself.

The one spec that cannot be transcribed literally is the recursive
`SimpleDate::add_days` (simple_date.rs). We replace it with a closed-form
characterization that the Verus proofs establish:

    for valid d, d.add_days(n) is the unique valid date r with
        EpochDelta::from_simple_date(r).delta() == from_simple_date(d).delta() + n

  - r is valid:       lemma_date_add_days_preserves_validity      (simple_date.rs)
  - delta shifts by n: lemma_from_simple_date_add_days             (epoch_delta.rs)
  - r is unique:      from_simple_date is injective on valid dates,
                      theorem_epoch_delta_congruent_preserves_comparison (epoch_delta.rs)

`add_days_rel` encodes this characterization.
"""

from z3 import And, If, Or


# ── period.rs / simple_date.rs ──────────────────────────────────────────────

def leap(year):
    """simple_date.rs: leap(year)"""
    return And(year % 4 == 0, Or(year % 100 != 0, year % 400 == 0))


def dim(year, month):
    """simple_date.rs: dim(year, month). Outside 1..12 the Verus array index
    is unspecified; this returns 31 there. Every caller guards with
    1 <= month <= 12 (is_valid, or add_months, whose month is always in range)."""
    return If(month == 2, If(leap(year), 29, 28),
              If(Or(month == 4, month == 6, month == 9, month == 11), 30, 31))


def is_valid(y, m, d):
    """simple_date.rs: SimpleDate::is_valid"""
    return And(1 <= m, m <= 12, 1 <= d, d <= dim(y, m))


def lt(a, b):
    """simple_date.rs: SimpleDate::lt (lexicographic on (y, m, d))"""
    (y1, m1, d1), (y2, m2, d2) = a, b
    return Or(y1 < y2,
              And(y1 == y2, m1 < m2),
              And(y1 == y2, m1 == m2, d1 < d2))


def eq(a, b):
    """simple_date.rs: SimpleDate::eq"""
    return And(a[0] == b[0], a[1] == b[1], a[2] == b[2])


def _min(a, b):
    return If(a <= b, a, b)


def add_months(date, n):
    """simple_date.rs: SimpleDate::add_months"""
    y, m, d = date
    y_ = y + (m - 1 + n) / 12
    m_ = 1 + ((m - 1 + n) % 12)
    d_ = _min(d, dim(y_, m_))
    return (y_, m_, d_)


def add_days_rel(date, n, result):
    """Closed-form characterization of SimpleDate::add_days (see module docstring).
    Holds iff result == date.add_days(n), for valid `date`."""
    return And(is_valid(*result), ed_from_simple_date(result) == ed_from_simple_date(date) + n)


def add_period_rel(date, years, months, days, result):
    """simple_date.rs: SimpleDate::add_period, as a relation on the result."""
    return add_days_rel(add_months(date, years * 12 + months), days, result)


# ── epoch_delta.rs ──────────────────────────────────────────────────────────

def years_since_epoch(y, m):
    return If(m <= 2, y - 1, y) - 2000


def months_since_march(m):
    return If(m <= 2, m + 9, m - 3)


def leap_correction(k):
    return k / 4 - k / 100 + k / 400


def ed_from_simple_date(date):
    """epoch_delta.rs: EpochDelta::from_simple_date(...).delta()"""
    y, m, d = date
    ye = years_since_epoch(y, m)
    days_by_years = 365 * ye + leap_correction(ye)
    me = months_since_march(m)
    days_by_months = (153 * me + 2) / 5
    days_by_dim = d - 1
    return days_by_years + days_by_months + days_by_dim


# ── alpha_beta.rs ───────────────────────────────────────────────────────────

EPOCH_ABS_MONTH = 2000 * 12 + 2


def year_of_alpha(alpha):
    return (EPOCH_ABS_MONTH + alpha) / 12


def month_of_alpha(alpha):
    return 1 + (EPOCH_ABS_MONTH + alpha) % 12


def ab_from_simple_date(date):
    """alpha_beta.rs: AlphaBeta::from_simple_date, as (alpha, beta)."""
    y, m, d = date
    alpha = years_since_epoch(y, m) * 12 + months_since_march(m)
    beta = d - 1
    return (alpha, beta)


def ab_lt(a, b):
    """alpha_beta.rs: AlphaBeta::lt"""
    return Or(a[0] < b[0], And(a[0] == b[0], a[1] < b[1]))


# ── Python-side domain restriction ──────────────────────────────────────────
# The Verus model is unbounded. The Python solvers bound every date to
# datetime.date's range [0001-01-01, 9999-12-31] so models can be turned back
# into concrete dates. Checks that depend on the bound state it explicitly.

YEAR_MIN, YEAR_MAX = 1, 9999


def in_python_range(date):
    return And(YEAR_MIN <= date[0], date[0] <= YEAR_MAX)
