"""
Checks reference_eval.py, the literal Python port of the Verus semantics that the
differential tests (tests/differential/) evaluate solver models with, against the
compiled Verus oracle, whose functions are proved equal to the Verus spec functions.

Coverage: leap, dim and is_valid on every year / month of years 1..9999 (plus negative
and >9999 years for leap and dim); lt, add_months and add_period on structured and
random cases.
"""

import calendar
import random

import pytest

from tests.differential import reference_eval as ref

from . import oracles
from .oracles import req

pytestmark = pytest.mark.semantics_vs_libraries

YEAR_BLOCKS = [(lo, min(lo + 999, 9999)) for lo in range(1, 10000, 1000)]


def _random_date(rng, lo=1, hi=9999):
    y, m = rng.randint(lo, hi), rng.randint(1, 12)
    return (y, m, rng.randint(1, calendar.monthrange(y % 400 + 400, m)[1]))


def assert_agree(requests, got, expected, what):
    bad = [(r, g, e) for r, g, e in zip(requests, got, expected) if g != e]
    assert not bad, f"{what}: {len(bad)} of {len(requests)} disagree, e.g. " + \
        "; ".join(f"{r!r}: reference_eval {g!r}, Verus oracle {e!r}" for r, g, e in bad[:5])


def _oracle(requests):
    answers = oracles.verus(requests)
    assert "none" not in answers
    return answers


# ── Calendar basics ─────────────────────────────────────────────────────────

def test_leap_and_dim():
    years = list(range(-1200, 10_401))
    requests = [req("leap", y) for y in years]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.leap(y)).lower() for y in years], expected, "reference_eval.leap")

    pairs = [(y, m) for y in years for m in range(1, 13)]
    requests = [req("dim", y, m) for y, m in pairs]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.dim(y, m)) for y, m in pairs], expected, "reference_eval.dim")


@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_is_valid(lo, hi):
    """Every year, every month 0..13, on the days where validity can change."""
    cases = [(y, m, d) for y in range(lo, hi + 1) for m in range(0, 14) for d in (0, 1, 28, 29, 30, 31, 32)]
    requests = [req("valid", *c) for c in cases]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.is_valid(c)).lower() for c in cases], expected, "reference_eval.is_valid")


def test_lt():
    rng = random.Random(12)
    pairs = [(_random_date(rng), _random_date(rng)) for _ in range(20_000)]
    pairs += [(a, (a[0], b[1], b[2])) for a, b in pairs[:5000]] + \
             [(a, (a[0], a[1], b[2])) for a, b in pairs[:5000]] + [(a, a) for a, _ in pairs[:2000]]
    requests = [req("lt", *a, *b) for a, b in pairs]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.lt(a, b)).lower() for a, b in pairs], expected, "reference_eval.lt")


# ── Date + period ───────────────────────────────────────────────────────────

MONTH_STEPS = [0, 1, -1, 2, -2, 11, -11, 12, -12, 13, -13, 24, -24, 1200, -1200, 4801, -4801]


def _add_months_cases():
    rng = random.Random(13)
    for y in (-401, -1, 0, 1, 4, 100, 400, 1900, 2000, 2024, 2100, 9999, 10_000):
        for m in range(1, 13):
            for d in (1, 28, 29, 30, 31):
                if d <= calendar.monthrange(y % 400 + 400, m)[1]:
                    for n in MONTH_STEPS:
                        yield (y, m, d), n
    for _ in range(20_000):
        yield _random_date(rng, -1000, 11_000), rng.randint(-30_000, 30_000)


def test_add_months():
    cases = list(_add_months_cases())
    requests = [req("add_months", *d, n) for d, n in cases]
    expected = _oracle(requests)
    show = lambda t: " ".join(map(str, t))
    assert_agree(requests, [show(ref.add_months(d, n)) for d, n in cases], expected, "reference_eval.add_months")


def _period_cases():
    rng = random.Random(14)
    for y in (1, 4, 100, 400, 1900, 2000, 2023, 2024, 2100, 9999):
        for m in range(1, 13):
            last = calendar.monthrange(y, m)[1]
            for d in sorted({1, 28, last}):
                for p in [(py, pm, pd) for py in (0, 1, -1) for pm in (0, 1, -1, 13)
                          for pd in (0, 1, -1, 31, -31, 366)]:
                    yield (y, m, d), p
    for _ in range(10_000):
        d = _random_date(rng, -1000, 11_000)
        yield d, (rng.randint(-50, 50), rng.randint(-600, 600), rng.randint(-40_000, 40_000))


def test_add_period():
    """reference_eval.add_period (used by the differential tests) equals the Verus
    add_period."""
    cases = list(_period_cases())
    requests = [req("add_period", *d, *p) for d, p in cases]
    expected = _oracle(requests)
    show = lambda t: " ".join(map(str, t))
    assert_agree(requests, [show(ref.add_period(d, p)) for d, p in cases], expected,
                 "reference_eval.add_period")

