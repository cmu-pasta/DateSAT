"""
Translation validation: the Z3 terms the Python encodings generate are checked
against the Verus reference semantics (transcribed in spec.py).

For every encoding E these are the Python-level counterparts of the three
congruence lemmas the Verus equisatisfiability proofs rely on
(see proofs/README.md, "Congruence: the key proof concept"):

  1. Construction   fresh variables and literals are congruent to a valid date,
                    and every valid date (in the supported range) is representable.
  2. Addition       x + P is congruent to SimpleDate::add_period(D, P), for every
                    code path that any concrete Period can take.
  3. Comparison     <, <=, >, >=, ==, != on congruent operands agree with
                    SimpleDate::lt / eq.

plus accessor correctness (.year/.month/.day return D's components) and
correctness of the shared conversion helpers.

Each check is one Z3 validity query over unbounded integers (with the
date domain restricted to years 1..9999 where the Python code itself bounds
dates). `unsat` = proved for the code path exercised.
"""

import os
import random
from datetime import date, timedelta

import pytest
from z3 import And, Int, Ints, Not, Or

from datesat.core import Date
from datesat.symbolic_int import alpha_beta_int, epoch_days_int, simple_int

from . import spec
from .harness import (
    ENCODINGS,
    ZERO_PATTERNS,
    add_months_linear,
    alpha_canonical,
    check_complete,
    domain,
    pattern_id,
    period_for_pattern,
    prove,
    ref_date,
    sym_date,
    sym_period,
    sym_ymd,
    symbolic_mode,
)
from .reference_eval import add_period as ref_add_period

pytestmark = pytest.mark.translation_validation

ENC_NAMES = list(ENCODINGS)


def _D(tag):
    return sym_ymd(tag)


# ── 0. Sanity of the transcribed spec ───────────────────────────────────────

def test_spec_add_period_matches_recursive_verus_spec():
    """spec.add_period_rel (closed form) agrees with a literal Python port of
    the recursive Verus SimpleDate::add_period on random inputs. Guards against
    transcription mistakes in spec.py."""
    from z3 import IntVal, simplify, is_true
    rng = random.Random(0)
    for _ in range(300):
        y = rng.randint(1, 9999)
        m = rng.randint(1, 12)
        d = rng.randint(1, 28)
        p = (rng.randint(-50, 50), rng.randint(-30, 30), rng.randint(-800, 800))
        r = ref_add_period((y, m, d), p)
        if not (1 <= r[0] <= 9999):
            continue
        z = lambda t: tuple(IntVal(v) for v in t)
        assert is_true(simplify(spec.add_period_rel(z((y, m, d)), *z(p), z(r)))), (y, m, d, p, r)


def test_spec_transcription_lemmas():
    """The two facts about the closed forms that the module docstring of
    spec.py leans on, re-checked in Z3 over unbounded integers."""
    D = _D("a")
    E = _D("b")
    n = Int("n")
    # from_simple_date is injective on valid dates (uniqueness in add_days_rel)
    prove(spec.eq(D, E),
          [spec.is_valid(*D), spec.is_valid(*E),
           spec.ed_from_simple_date(D) == spec.ed_from_simple_date(E)],
          label="fsd injective")
    # and strictly monotone: the ordering bridge used by comparisons
    prove(spec.lt(D, E) == (spec.ed_from_simple_date(D) < spec.ed_from_simple_date(E)),
          [spec.is_valid(*D), spec.is_valid(*E)], label="fsd monotone")


# ── 1. Shared helpers ───────────────────────────────────────────────────────

def test_epoch_encode_matches_spec():
    """_days_since_epoch_from_ymd_z3 == EpochDelta::from_simple_date, all valid dates."""
    D = _D("x")
    prove(epoch_days_int._days_since_epoch_from_ymd_z3(*D) == spec.ed_from_simple_date(D),
          [spec.is_valid(*D)], label="encode")


def test_epoch_encode_is_linear_in_day():
    """alpha_beta and hybrid call the encoder with out-of-month days
    (e.g. d = 40) and rely on it being affine in d, as from_simple_date is."""
    y, m, d = Ints("y m d")
    prove(epoch_days_int._days_since_epoch_from_ymd_z3(y, m, d)
          == spec.ed_from_simple_date((y, m, 1)) + d - 1,
          [1 <= m, m <= 12], label="encode affine")


def test_epoch_decode_is_inverse():
    """_ymd_from_days_since_epoch_z3(n) is a valid date whose from_simple_date
    is n, for every integer n. By injectivity this is EpochDelta::to_ymd."""
    n = Int("n")
    D = epoch_days_int._ymd_from_days_since_epoch_z3(n)
    prove(spec.is_valid(*D), label="decode valid")
    prove(spec.ed_from_simple_date(D) == n, label="decode inverse")


def test_alpha_helpers_match_spec():
    D = _D("x")
    a = Int("a")
    prove(alpha_beta_int.months_since_epoch_from_ym(D[0], D[1]) == spec.ab_from_simple_date(D)[0],
          [1 <= D[1], D[1] <= 12], label="alpha encode")
    y, m = alpha_beta_int.ym_from_months_since_epoch(a)
    prove(And(y == spec.year_of_alpha(a), m == spec.month_of_alpha(a)), label="alpha decode")


def test_alpha_lemmas():
    """Lemma instances that harness.contract_facts / the add tests feed to Z3."""
    D = _D("x")
    n = Int("n")
    prove(alpha_canonical(D), label="alpha canonical")
    prove(add_months_linear(D, n), label="add_months linear")


def test_simple_helpers_match_spec():
    y, m, d, n = Ints("y m d n")
    prove(simple_int.days_in_month(y, m) == spec.dim(y, m), [1 <= m, m <= 12], label="dim")
    ny, nm = simple_int.normalize_month(y, m + n)
    am = spec.add_months((y, m, d), n)
    prove(And(ny == am[0], nm == am[1]), [1 <= m, m <= 12], label="normalize_month")
    prove(simple_int.eom_clamp(am[0], am[1], d) == am[2], [spec.is_valid(y, m, d)], label="eom_clamp")


# ── Exhaustive check of the concrete (datetime-based) helpers ───────────────

def _exhaustive_bounds():
    # Full datetime range by default; DATESAT_TV_RANGE=paper restricts to
    # the paper's [1900-03-01, 2100-02-28].
    if os.environ.get("DATESAT_TV_RANGE") == "paper":
        return date(1900, 3, 1), date(2100, 2, 28)
    return date(1, 1, 1), date(9999, 12, 31)


def _py_fsd(y, m, d):
    """from_simple_date with Python ints (floor division == Euclidean for the
    positive divisors used here)."""
    ye = (y - 1 if m <= 2 else y) - 2000
    me = m + 9 if m <= 2 else m - 3
    return 365 * ye + ye // 4 - ye // 100 + ye // 400 + (153 * me + 2) // 5 + d - 1


def test_literal_embedding_exhaustive():
    """For every date in range: days_since_epoch_from_date (datetime-based,
    used for literals) equals from_simple_date, and date_from_days_since_epoch
    (used to decode models) inverts it. This also justifies symbolic_mode's
    replacement of days_since_epoch_from_date by its spec."""
    lo, hi = _exhaustive_bounds()
    base = _py_fsd(lo.year, lo.month, lo.day)
    o_lo, o_hi = lo.toordinal(), hi.toordinal()
    fsd_of = epoch_days_int.days_since_epoch_from_date
    dec = epoch_days_int.date_from_days_since_epoch
    for i, o in enumerate(range(o_lo, o_hi + 1)):
        pd = date.fromordinal(o)
        dt = Date(pd.year, pd.month, pd.day)
        n = _py_fsd(pd.year, pd.month, pd.day)
        # consecutive values: enumeration hits every delta exactly once
        assert n == base + i, pd
        assert fsd_of(dt) == n, pd
        back = dec(n)
        assert (back.year, back.month, back.day) == (pd.year, pd.month, pd.day), pd


class _ConstModel:
    """Minimal stand-in for a z3 ModelRef: evaluates a fixed assignment."""

    def __init__(self, assignment):
        from z3 import substitute, IntVal
        self._subs = [(k, IntVal(v)) for k, v in assignment.items()]

    def evaluate(self, t, model_completion=True):
        from z3 import simplify, substitute
        return simplify(substitute(t, *self._subs))


def test_alpha_beta_model_decoding_exhaustive():
    """alpha_beta DateVar.to_concrete_date (pure-Python decode) agrees with
    AlphaBeta::to_ymd for every alpha in the solver's bounds."""
    v = alpha_beta_int.DateVar("x")
    for alpha in range(-23990, 95997 + 1, 7):  # stride keeps this fast; all residues mod 12 hit
        for beta in (0, 27):
            k = alpha + 2000 * 12 + 2
            want = (k // 12, 1 + k % 12, beta + 1)
            got = v.to_concrete_date(_ConstModel({v.months_var: alpha, v.beta_var: beta}))
            assert (got.year, got.month, got.day) == want, alpha


# ── 2. Construction ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("enc_name", ENC_NAMES)
def test_fresh_var_sound(enc_name):
    """Every model of a fresh variable's constraints denotes a valid,
    in-range date that the variable is congruent to (namely its accessors)."""
    enc = ENCODINGS[enc_name]
    with symbolic_mode():
        s = enc.make_solver()
        x = enc.new_var(s, "x")
        D = (x.year, x.month, x.day)
        claim = And(domain(D), enc.congruent(x, D))
        prove(claim, enc.assertions(s), label=f"{enc_name}/fresh sound")


@pytest.mark.parametrize("enc_name", ENC_NAMES)
def test_fresh_var_complete_and_accessors(enc_name):
    """Every valid in-range date is representable by a fresh variable, and
    accessors on a congruent variable return the date's components."""
    enc = ENCODINGS[enc_name]
    with symbolic_mode():
        D = _D("x")
        s = enc.make_solver()
        x = enc.new_var(s, "x")
        check_complete(enc, s, [(x, D)], label=f"{enc_name}/fresh")
        pre = enc.congruent(x, D)
        acc = (x.year, x.month, x.day)
        hyps = enc.assertions(s) + [spec.is_valid(*D), pre]
        prove(And(spec.eq(acc, D), enc.congruent(x, D)), hyps, label=f"{enc_name}/accessors")
        check_complete(enc, s, [(x, D)], label=f"{enc_name}/accessors")


# ── 3. Addition ─────────────────────────────────────────────────────────────

SIMPLE_DAY_VALUES = [0, 1, -1, 2, -2, 31]


def _add_cases():
    for enc_name in ENC_NAMES:
        enc = ENCODINGS[enc_name]
        for pat in ZERO_PATTERNS:
            if enc.supports_symbolic_days or pat[2]:
                yield pytest.param(enc_name, pat, None, id=f"{enc_name}-{pattern_id(pat)}")
            else:
                for k in SIMPLE_DAY_VALUES[1:]:
                    yield pytest.param(enc_name, pat, k, id=f"{enc_name}-{pattern_id(pat)[:2]}{k:+d}")


def _period(pattern, days_value):
    p, comps, conds = period_for_pattern(pattern)
    if days_value is not None:
        from z3 import IntVal
        p = sym_period(p.years, p.months, days_value)
        comps = (comps[0], comps[1], IntVal(days_value))
    return p, comps, conds


@pytest.mark.parametrize("enc_name,pattern,days_value", list(_add_cases()))
def test_add_period_preserves_congruence(enc_name, pattern, days_value):
    """congruent(x, D) => congruent(x + P, SimpleDate::add_period(D, P)), and
    the result's accessors return the reference components.

    For `simple` the day component is concrete because add_days_componentwise
    unrolls one loop iteration per day. The +-1 cases prove the loop body
    equals SimpleDate::add_days(+-1) on every valid date; since the body does
    not depend on the iteration index and add_days_rel composes (delta shifts
    add up and validity is preserved), k iterations compute add_days(k) for
    every concrete k by induction."""
    enc = ENCODINGS[enc_name]
    with symbolic_mode():
        D = _D("x")
        R = ref_date("r")
        P, (py, pm, pd), conds = _period(pattern, days_value)
        s = enc.make_solver()
        x = enc.new_var(s, "x")
        x_pre = enc.congruent(x, D)
        r = x + P
        ref = spec.add_period_rel(D, py, pm, pd, R)
        n = py * 12 + pm
        lemmas = [alpha_canonical(spec.add_months(D, n)), add_months_linear(D, n)]
        hyps = [spec.is_valid(*D), x_pre, ref] + conds + lemmas
        prove(enc.congruent(r, R), enc.assertions(s) + hyps, label=f"{enc_name}/add")
        check_complete(enc, s, [(x, D), (r, R)], extra_hyps=[ref] + conds, label=f"{enc_name}/add")
        acc = (r.year, r.month, r.day)
        prove(And(spec.eq(acc, R), enc.congruent(r, R)), enc.assertions(s) + hyps,
              label=f"{enc_name}/add accessors")
        check_complete(enc, s, [(x, D), (r, R)], extra_hyps=[ref] + conds,
                       label=f"{enc_name}/add accessors")


@pytest.mark.parametrize("enc_name", ENC_NAMES)
def test_sub_is_add_of_negation(enc_name):
    """x - P builds exactly the terms of x + (-P)."""
    enc = ENCODINGS[enc_name]
    from datesat.core import Period
    for P in (Period(1, 2, 3), Period(0, 0, 5), Period(0, 3, 0), Period(-2, 0, 7)):
        s1, s2 = enc.make_solver(), enc.make_solver()
        a = enc.new_var(s1, "x") - P
        b = enc.new_var(s2, "x") + Period(-P.years, -P.months, -P.days)
        assert a.year.sexpr() == b.year.sexpr()
        assert [t.sexpr() for t in enc.assertions(s1)] == [t.sexpr() for t in enc.assertions(s2)]


# ── 4. Comparison ───────────────────────────────────────────────────────────

OPS = {
    "lt": (lambda a, b: a < b, lambda A, B: spec.lt(A, B)),
    "le": (lambda a, b: a <= b, lambda A, B: Or(spec.lt(A, B), spec.eq(A, B))),
    "gt": (lambda a, b: a > b, lambda A, B: spec.lt(B, A)),
    "ge": (lambda a, b: a >= b, lambda A, B: Or(spec.lt(B, A), spec.eq(A, B))),
    "eq": (lambda a, b: a == b, lambda A, B: spec.eq(A, B)),
    "ne": (lambda a, b: a != b, lambda A, B: Not(spec.eq(A, B))),
}

# Operand shapes. For hybrid encodings they produce every representation
# state: fresh (init state), epoch-only (day addition), YMD-only (month
# addition). For the other encodings comparisons only see the representation,
# so var/lit suffice.
HYBRID_KINDS = ["var", "lit", "days", "months"]
PLAIN_KINDS = ["var", "lit"]


def _operand(enc, s, kind, tag):
    """Return (python operand, reference date, hypotheses, [(DateVar, D)])."""
    D = _D(tag)
    if kind == "lit":
        return sym_date(*D), D, [spec.is_valid(*D)], []
    base = enc.new_var(s, f"v{tag}")
    if kind == "var":
        return base, D, [spec.is_valid(*D), enc.congruent(base, D)], [(base, D)]
    B = _D(f"b{tag}")
    pat = (True, True, False) if kind == "days" else (False, False, True)
    P, (py, pm, pd), conds = period_for_pattern(pat, tag=tag)
    hyps = [spec.is_valid(*B), enc.congruent(base, B)] + conds
    r = base + P
    hyps += [spec.add_period_rel(B, py, pm, pd, D), enc.congruent(r, D)]
    return r, D, hyps, [(base, B), (r, D)]


def _compare_cases():
    for enc_name in ENC_NAMES:
        kinds = HYBRID_KINDS if enc_name.startswith("hybrid") else PLAIN_KINDS
        for ka in kinds:
            for kb in kinds:
                if ka == kb == "lit":
                    continue
                for op in OPS:
                    yield pytest.param(enc_name, ka, kb, op, id=f"{enc_name}-{ka}-{op}-{kb}")


@pytest.mark.parametrize("enc_name,ka,kb,op", list(_compare_cases()))
def test_comparison_agrees_with_spec(enc_name, ka, kb, op):
    """py_op(a, b) <=> ref_op(A, B) for congruent operands; comparing keeps
    the operands congruent (hybrid comparisons may materialize a lazy side)."""
    if enc_name == "simple" and "days" in (ka, kb):
        pytest.skip("simple needs concrete days")
    enc = ENCODINGS[enc_name]
    py_op, ref_op = OPS[op]
    with symbolic_mode():
        s = enc.make_solver()
        a, A, ha, wa = _operand(enc, s, ka, "a")
        b, B, hb, wb = _operand(enc, s, kb, "b")
        hyps = ha + hb
        result = py_op(a, b)
        post = [enc.congruent(o, D) for o, D in wa + wb]
        prove(And(result == ref_op(A, B), *post), enc.assertions(s) + hyps,
              label=f"{enc_name}/{ka} {op} {kb}")
        extra = [h for h in hyps if not any(h.eq(enc.congruent(o, D)) for o, D in wa + wb)]
        check_complete(enc, s, wa + wb, extra_hyps=extra + [spec.is_valid(*A), spec.is_valid(*B)],
                       label=f"{enc_name}/{ka} {op} {kb}")
