"""
Spec adequacy: does the Verus reference semantics (proofs/src/simple_date.rs) describe
the real calendar?

The Verus oracle (proofs/src/oracle.rs, proved equal to the spec functions) is compared
with two independent implementations of the proleptic Gregorian calendar:

  * Python's datetime / dateutil.relativedelta, over every date in its range
    0001-01-01..9999-12-31, which is also the domain of the DateSAT solvers.
  * java.time, the same checks in that range, plus random checks far outside it.

What "agrees" means for each spec function:
  * is_valid(y, m, d)   <=> datetime.date(y, m, d) / LocalDate.of(y, m, d) accepts it
  * lt                  <=> date ordering
  * from_simple_date    == days since 2000-03-01
  * add_days(n)         == date + n days
  * add_months(n)       == date + relativedelta(months=n) / plusMonths(n)
  * add_period(y, m, d) == date + relativedelta(years=y, months=m, days=d) /
                           plus(Period.of(y, m, d))
"""

import calendar
import datetime
import random

import pytest
from dateutil.relativedelta import relativedelta

from . import oracles
from .oracles import date_answer, req

pytestmark = pytest.mark.spec_adequacy

EPOCH = datetime.date(2000, 3, 1)
YEAR_BLOCKS = [(lo, min(lo + 999, 9999)) for lo in range(1, 10000, 1000)]
MONTH_STEPS = [1, -1, 2, -2, 11, -11, 12, -12, 13, -13, 24, -24, 48, -48, 1200, -1200]
# Day offsets around month, year, 4-year, century and 400-year lengths.
DAY_STEPS = [0, 1, -1, 27, 28, 29, 30, 31, -28, -29, -30, -31, 59, 60, 365, 366, -365, -366,
             1461, -1461, 36524, 36525, -36524, 146097, -146097]
SPECIAL_YEARS = [1, 2, 3, 4, 99, 100, 101, 399, 400, 401, 1600, 1700, 1800, 1900, 1999, 2000,
                 2001, 2003, 2004, 2023, 2024, 2100, 2400, 9996, 9998, 9999]


def _ymd(d):
    return (d.year, d.month, d.day)


def _dates(lo, hi):
    d, end = datetime.date(lo, 1, 1), datetime.date(hi, 12, 31)
    while True:
        yield d
        if d == end:
            return
        d += datetime.timedelta(1)


def _py(f):
    """Run a datetime computation; None when the result leaves years 1..9999."""
    try:
        return _ymd(f())
    except (ValueError, OverflowError):
        return None


def _in_range(t):
    return t is not None and 1 <= t[0] <= 9999


def assert_agree(requests, got, expected, what):
    bad = [(r, g, e) for r, g, e in zip(requests, got, expected) if g != e]
    assert not bad, f"{what}: {len(bad)} of {len(requests)} disagree, e.g. " + \
        "; ".join(f"{r!r}: oracle {g!r}, expected {e!r}" for r, g, e in bad[:5])


def check_dates(oracle, requests, expected, what):
    """Compare date answers. Where the library has no answer (result outside years
    1..9999) the oracle must put the result outside that range too."""
    got = [date_answer(a) for a in oracle(requests)]
    assert None not in got, f"{what}: oracle overflowed on {requests[got.index(None)]!r}"
    got = [g if _in_range(g) or e is not None else None for g, e in zip(got, expected)]
    assert_agree(requests, got, expected, what)


# ── Exhaustive over Python's range, in year blocks ──────────────────────────

@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_validity_exhaustive(oracle, lo, hi):
    """Every (y, m, d) with m in 0..13 and d in 0..32: is_valid <=> the library accepts it."""
    requests, expected = [], []
    for y in range(lo, hi + 1):
        for m in range(0, 14):
            for d in range(0, 33):
                requests.append(req("valid", y, m, d))
                try:
                    datetime.date(y, m, d)
                    expected.append("true")
                except ValueError:
                    expected.append("false")
    assert_agree(requests, oracle(requests), expected, "is_valid")


@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_leap_and_dim_exhaustive(lo, hi):
    requests = [req("leap", y) for y in range(lo, hi + 1)]
    expected = [str(calendar.isleap(y)).lower() for y in range(lo, hi + 1)]
    assert_agree(requests, oracles.verus(requests), expected, "leap")
    requests = [req("dim", y, m) for y in range(lo, hi + 1) for m in range(1, 13)]
    expected = [str(calendar.monthrange(y, m)[1]) for y in range(lo, hi + 1) for m in range(1, 13)]
    assert_agree(requests, oracles.verus(requests), expected, "dim")


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_epoch_delta_successor_and_order_exhaustive(oracle, lo, hi):
    """Every date: from_simple_date == days since 2000-03-01; add_days(+-1) == the
    next/previous day; lt agrees with the order of consecutive days."""
    dates = list(_dates(lo, hi))
    requests = [req("from_simple_date", *_ymd(d)) for d in dates]
    assert_agree(requests, oracle(requests), [str((d - EPOCH).days) for d in dates], "from_simple_date")
    for n in (1, -1):
        requests = [req("add_days", *_ymd(d), n) for d in dates]
        expected = [_py(lambda: d + datetime.timedelta(n)) for d in dates]
        check_dates(oracle, requests, expected, f"add_days({n})")
    pairs = [(a, b) for a, b in zip(dates, dates[1:])]
    requests = [req("lt", *_ymd(a), *_ymd(b)) for a, b in pairs] + \
               [req("lt", *_ymd(b), *_ymd(a)) for a, b in pairs] + \
               [req("lt", *_ymd(a), *_ymd(a)) for a in dates]
    expected = ["true"] * len(pairs) + ["false"] * (len(pairs) + len(dates))
    assert_agree(requests, oracle(requests), expected, "lt")


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_add_months_exhaustive_months(oracle, lo, hi):
    """Every (year, month), on day 1, 15 and the days where end-of-month clamping can
    apply (28..31), for month steps up to +-100 years."""
    requests, expected = [], []
    for y in range(lo, hi + 1):
        for m in range(1, 13):
            for d in (1, 15, 28, 29, 30, 31):
                if d > calendar.monthrange(y, m)[1]:
                    continue
                base = datetime.date(y, m, d)
                for n in MONTH_STEPS:
                    requests.append(req("add_months", y, m, d, n))
                    expected.append(_py(lambda: base + relativedelta(months=n)))
    check_dates(oracle, requests, expected, "add_months")


# ── Structured and random date + period ─────────────────────────────────────

def _period_grid():
    for py in (0, 1, -1, 4, -4, 100, -100, 400):
        for pm in (0, 1, -1, 11, -11, 12, 13, -13):
            for pd in (0, 1, -1, 28, -29, 30, -31, 365, -366, 1461):
                yield (py, pm, pd)


def _structured_add_period_cases():
    for y in SPECIAL_YEARS:
        for m in range(1, 13):
            last = calendar.monthrange(y, m)[1]
            for d in sorted({1, 15, 28, last} & set(range(1, last + 1))):
                for p in _period_grid():
                    yield (y, m, d), p


def _random_date(rng, lo=1, hi=9999):
    y, m = rng.randint(lo, hi), rng.randint(1, 12)
    # y % 400 + 400 has the same calendar as y and is a year `calendar` accepts
    return (y, m, rng.randint(1, calendar.monthrange(y % 400 + 400, m)[1]))


def _random_add_period_cases(rng, count, lo=1, hi=9999):
    for _ in range(count):
        date = _random_date(rng, lo, hi)
        p = (rng.choice([0, rng.randint(-3, 3), rng.randint(-500, 500)]),
             rng.choice([0, rng.randint(-14, 14), rng.randint(-6000, 6000)]),
             rng.choice([0, rng.randint(-62, 62), rng.randint(-200_000, 200_000)]))
        yield date, p


def _months_stay_in_range(date, p):
    """relativedelta adds years and months first; skip cases where that midpoint
    leaves its range although the final result might not (the spec has no range)."""
    return 1 <= date[0] + (date[1] - 1 + 12 * p[0] + p[1]) // 12 <= 9999


def _check_add_period(oracle, cases, what):
    cases = [(d, p) for d, p in cases if _months_stay_in_range(d, p)]
    requests = [req("add_period", *d, *p) for d, p in cases]
    expected = [_py(lambda: datetime.date(*d) + relativedelta(years=p[0], months=p[1], days=p[2]))
                for d, p in cases]
    check_dates(oracle, requests, expected, what)
    return len(cases)


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
def test_add_period_structured(oracle):
    """Special years (century, 400-year, leap and range-edge years), every month, on
    the first, middle and last days, against a grid of periods mixing zero and
    non-zero components."""
    assert _check_add_period(oracle, _structured_add_period_cases(), "add_period (structured)") > 100_000


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
def test_add_period_random(oracle):
    assert _check_add_period(oracle, _random_add_period_cases(random.Random(1), 300_000),
                             "add_period (random)") > 250_000


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
def test_add_days_random(oracle):
    rng = random.Random(2)
    cases = [(_random_date(rng), rng.choice(DAY_STEPS + [rng.randint(-3_652_058, 3_652_058)]))
             for _ in range(200_000)]
    requests = [req("add_days", *d, n) for d, n in cases]
    expected = [_py(lambda: datetime.date(*d) + datetime.timedelta(n)) for d, n in cases]
    check_dates(oracle, requests, expected, "add_days (random)")


@pytest.mark.parametrize("oracle", [oracles.verus, oracles.java], ids=["verus", "java"])
def test_lt_random(oracle):
    rng = random.Random(3)
    pairs = [(_random_date(rng), _random_date(rng)) for _ in range(300_000)]
    pairs += [(a, (a[0], a[1], min(b[2], calendar.monthrange(a[0], a[1])[1])))  # same month
              for a, b in pairs[:50_000]]
    requests = [req("lt", *a, *b) for a, b in pairs]
    expected = [str(datetime.date(*a) < datetime.date(*b)).lower() for a, b in pairs]
    assert_agree(requests, oracle(requests), expected, "lt (random)")


def test_epoch_to_ymd_sample():
    """EpochDelta::to_ymd is EPOCH.add_days(delta); sampled because the oracle steps
    month by month from 2000-03-01."""
    lo, hi = (datetime.date(1, 1, 1) - EPOCH).days, (datetime.date(9999, 12, 31) - EPOCH).days
    deltas = sorted({lo, hi, 0, -1, 1} | set(random.Random(4).sample(range(lo, hi + 1), 1500)))
    requests = [req("epoch_to_ymd", n) for n in deltas]
    check_dates(oracles.verus, requests, [_ymd(EPOCH + datetime.timedelta(n)) for n in deltas],
                "epoch_to_ymd")


# ── Beyond Python's range: Verus oracle vs java.time ────────────────────────

FAR = (-50_000, 50_000)


def _verus_equals_java(requests, what):
    v, j = oracles.verus(requests), oracles.java(requests)
    assert "none" not in v and "none" not in j, what
    assert_agree(requests, v, j, what)


def test_java_validity_beyond_python_range():
    rng = random.Random(5)
    years = sorted(set(rng.sample(range(*FAR), 3000)) | {0, -1, -4, -100, -400, 10_000, 10_400})
    _verus_equals_java([req("valid", y, m, d) for y in years for m in range(0, 14) for d in range(0, 33)],
                       "is_valid beyond 1..9999")


def test_java_epoch_delta_and_order_beyond_python_range():
    rng = random.Random(6)
    dates = [_random_date(rng, *FAR) for _ in range(200_000)]
    _verus_equals_java([req("from_simple_date", *d) for d in dates], "from_simple_date beyond 1..9999")
    _verus_equals_java([req("lt", *a, *b) for a, b in zip(dates, dates[1:])], "lt beyond 1..9999")


def test_java_add_period_beyond_python_range():
    cases = list(_random_add_period_cases(random.Random(7), 200_000, *FAR))
    _verus_equals_java([req("add_period", *d, *p) for d, p in cases], "add_period beyond 1..9999")
    rng = random.Random(8)
    cases = [(_random_date(rng, *FAR), rng.choice(MONTH_STEPS)) for _ in range(100_000)]
    _verus_equals_java([req("add_months", *d, n) for d, n in cases], "add_months beyond 1..9999")
