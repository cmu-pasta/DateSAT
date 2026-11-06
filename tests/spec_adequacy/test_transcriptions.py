"""
Closes the hand-transcription gap of tests/translation_validation/: the Z3 spec
(spec.py), the literal Python port (reference_eval.py) and the Python epoch formula
(_py_fsd) were copied from the Verus spec by hand. Here each is compared with the
compiled Verus oracle, whose functions are proved equal to the Verus spec functions.

spec.py builds Z3 terms, so it is evaluated by substituting concrete values into a
term built once over free variables and simplifying. Coverage:

  * from_simple_date (all three copies), dim, leap, is_valid: every date / month /
    year of years 1..9999, plus negative and >9999 years for the arithmetic helpers.
  * add_months, add_period / add_period_rel, lt, eq, alpha helpers: structured and
    random cases.

spec.add_days_rel / add_period_rel are relations (the closed form of the recursive
add_days); we check that they hold for the oracle's result and fail for its
neighbouring days.
"""

import calendar
import datetime
import random

import pytest
from z3 import Int, IntVal, is_true, simplify, substitute

from tests.translation_validation import reference_eval as ref
from tests.translation_validation import spec
from tests.translation_validation.test_translation_validation import _py_fsd

from . import oracles
from .oracles import date_answer, req

pytestmark = pytest.mark.spec_adequacy

YEAR_BLOCKS = [(lo, min(lo + 999, 9999)) for lo in range(1, 10000, 1000)]


class Term:
    """A spec.py term over free Int variables, evaluated on concrete values."""

    def __init__(self, build, arity):
        self.vars = [Int(f"v{i}") for i in range(arity)]
        out = build(*self.vars)
        self.outs = list(out) if isinstance(out, tuple) else [out]

    def __call__(self, *vals):
        subst = [(v, IntVal(x)) for v, x in zip(self.vars, vals)]
        res = [simplify(substitute(o, *subst)) for o in self.outs]
        res = [str(is_true(r)).lower() if r.sort().name() == "Bool" else str(r.as_long()) for r in res]
        return " ".join(res)


def _dates(lo, hi):
    d, end = datetime.date(lo, 1, 1), datetime.date(hi, 12, 31)
    while True:
        yield (d.year, d.month, d.day)
        if d == end:
            return
        d += datetime.timedelta(1)


def _random_date(rng, lo=1, hi=9999):
    y, m = rng.randint(lo, hi), rng.randint(1, 12)
    return (y, m, rng.randint(1, calendar.monthrange(y % 400 + 400, m)[1]))


def assert_agree(requests, got, expected, what):
    bad = [(r, g, e) for r, g, e in zip(requests, got, expected) if g != e]
    assert not bad, f"{what}: {len(bad)} of {len(requests)} disagree, e.g. " + \
        "; ".join(f"{r!r}: transcription {g!r}, Verus oracle {e!r}" for r, g, e in bad[:5])


def _oracle(requests):
    answers = oracles.verus(requests)
    assert "none" not in answers
    return answers


# ── from_simple_date: every date, all three transcriptions ──────────────────

@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_from_simple_date_exhaustive(lo, hi):
    dates = list(_dates(lo, hi))
    expected = _oracle([req("from_simple_date", *d) for d in dates])
    requests = [req("from_simple_date", *d) for d in dates]
    assert_agree(requests, [str(_py_fsd(*d)) for d in dates], expected, "_py_fsd")
    term = Term(lambda y, m, d: spec.ed_from_simple_date((y, m, d)), 3)
    assert_agree(requests, [term(*d) for d in dates], expected, "spec.ed_from_simple_date")


def test_from_simple_date_outside_python_range():
    rng = random.Random(11)
    dates = [_random_date(rng, -50_000, 50_000) for _ in range(20_000)]
    requests = [req("from_simple_date", *d) for d in dates]
    expected = _oracle(requests)
    assert_agree(requests, [str(_py_fsd(*d)) for d in dates], expected, "_py_fsd")
    term = Term(lambda y, m, d: spec.ed_from_simple_date((y, m, d)), 3)
    assert_agree(requests, [term(*d) for d in dates], expected, "spec.ed_from_simple_date")


# ── Calendar basics ─────────────────────────────────────────────────────────

def test_leap_and_dim():
    years = list(range(-1200, 10_401))
    requests = [req("leap", y) for y in years]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.leap(y)).lower() for y in years], expected, "reference_eval.leap")
    term = Term(spec.leap, 1)
    assert_agree(requests, [term(y) for y in years], expected, "spec.leap")

    pairs = [(y, m) for y in years for m in range(1, 13)]
    requests = [req("dim", y, m) for y, m in pairs]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.dim(y, m)) for y, m in pairs], expected, "reference_eval.dim")
    term = Term(spec.dim, 2)
    assert_agree(requests, [term(y, m) for y, m in pairs], expected, "spec.dim")


@pytest.mark.parametrize("lo,hi", YEAR_BLOCKS, ids=[f"{lo}-{hi}" for lo, hi in YEAR_BLOCKS])
def test_is_valid(lo, hi):
    """Every year, every month 0..13, on the days where validity can change."""
    cases = [(y, m, d) for y in range(lo, hi + 1) for m in range(0, 14) for d in (0, 1, 28, 29, 30, 31, 32)]
    requests = [req("valid", *c) for c in cases]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.is_valid(c)).lower() for c in cases], expected, "reference_eval.is_valid")
    term = Term(spec.is_valid, 3)
    assert_agree(requests, [term(*c) for c in cases], expected, "spec.is_valid")


def test_lt_and_eq():
    rng = random.Random(12)
    pairs = [(_random_date(rng), _random_date(rng)) for _ in range(20_000)]
    pairs += [(a, (a[0], b[1], b[2])) for a, b in pairs[:5000]] + \
             [(a, (a[0], a[1], b[2])) for a, b in pairs[:5000]] + [(a, a) for a, _ in pairs[:2000]]
    requests = [req("lt", *a, *b) for a, b in pairs]
    expected = _oracle(requests)
    assert_agree(requests, [str(ref.lt(a, b)).lower() for a, b in pairs], expected, "reference_eval.lt")
    lt = Term(lambda *v: spec.lt(v[:3], v[3:]), 6)
    assert_agree(requests, [lt(*a, *b) for a, b in pairs], expected, "spec.lt")
    # SimpleDate::eq is component-wise equality; lt in both directions decides it
    eq = Term(lambda *v: spec.eq(v[:3], v[3:]), 6)
    back = _oracle([req("lt", *b, *a) for a, b in pairs])
    expected_eq = [str(f == "false" and g == "false").lower() for f, g in zip(expected, back)]
    assert_agree(requests, [eq(*a, *b) for a, b in pairs], expected_eq, "spec.eq")


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
    term = Term(lambda y, m, d, n: spec.add_months((y, m, d), n), 4)
    assert_agree(requests, [term(*d, n) for d, n in cases], expected, "spec.add_months")


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
    add_period; spec.add_period_rel holds for the Verus result and fails for the
    days next to it."""
    cases = list(_period_cases())
    requests = [req("add_period", *d, *p) for d, p in cases]
    expected = _oracle(requests)
    show = lambda t: " ".join(map(str, t))
    assert_agree(requests, [show(ref.add_period(d, p)) for d, p in cases], expected,
                 "reference_eval.add_period")

    rel = Term(lambda *v: spec.add_period_rel(v[0:3], v[3], v[4], v[5], v[6:9]), 9)
    results = [date_answer(e) for e in expected]
    assert_agree(requests, [rel(*d, *p, *r) for (d, p), r in zip(cases, results)], ["true"] * len(cases),
                 "spec.add_period_rel(oracle result)")

    sample = list(zip(cases, results))[::7]
    neighbours = _oracle([req("add_days", *r, k) for _, r in sample for k in (1, -1)])
    wrong = [((d, p), date_answer(nb)) for ((d, p), _), nb in zip([s for s in sample for _ in (1, -1)], neighbours)]
    assert_agree([req("add_period", *d, *p) for (d, p), _ in wrong],
                 [rel(*d, *p, *nb) for (d, p), nb in wrong], ["false"] * len(wrong),
                 "spec.add_period_rel(neighbour of oracle result)")


# ── Alpha-beta helpers ──────────────────────────────────────────────────────

def test_alpha_helpers():
    alphas = list(range(-30_000, 100_001, 7)) + list(range(-30, 31))
    for op, f in (("year_of_alpha", spec.year_of_alpha), ("month_of_alpha", spec.month_of_alpha)):
        requests = [req(op, a) for a in alphas]
        term = Term(f, 1)
        assert_agree(requests, [term(a) for a in alphas], _oracle(requests), f"spec.{op}")
    rng = random.Random(15)
    dates = [_random_date(rng, -1000, 11_000) for _ in range(20_000)]
    dates += [(y, m, 1) for y in (1, 1999, 2000, 2001, 9999) for m in range(1, 13)]
    requests = [req("ab_from_simple_date", *d) for d in dates]
    term = Term(lambda y, m, d: spec.ab_from_simple_date((y, m, d)), 3)
    assert_agree(requests, [term(*d) for d in dates], _oracle(requests), "spec.ab_from_simple_date")
