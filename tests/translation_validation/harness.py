"""
Harness for translation validation of the Python encodings against spec.py.

The idea: the Python DateVar methods *return Z3 terms*, so we call them on
symbolic inputs and ask Z3 whether the terms they produced can ever disagree
with the Verus reference semantics. An `unsat` answer is a proof about the
exact terms the implementation generates (for that code path).

Three pieces make the Python code runnable on symbolic inputs without editing it:

  * `sym_period` / `sym_date` build Period / Date objects whose fields are Z3
    Ints, bypassing the constructors' concrete-int validation.
  * `symbolic_mode` lifts `IntVal` in the encoding modules to pass Z3 terms
    through unchanged (it is the identity on values), and replaces
    `days_since_epoch_from_date`, the only helper that calls datetime, by its
    spec. That replacement is justified separately by an exhaustive check
    (test_literal_embedding_exhaustive).
  * `symbolic_mode` also replaces the decoder `_ymd_from_days_since_epoch_z3`
    by its contract: each call returns fresh constants (y, m, d) together with
    the facts is_valid(y, m, d) and from_simple_date(y, m, d) == n. That
    contract is proved for the real decoder in test_epoch_decode_is_inverse,
    and it determines (y, m, d) uniquely (from_simple_date is injective on
    valid dates), so using it is ordinary modular verification. It keeps the
    nonlinear 400/100/4-year decomposition out of every downstream query.
  * Likewise the encoder `_days_since_epoch_from_ymd_z3(y, m, d)` is replaced by
    a fresh constant e with the fact `1 <= m <= 12 ==> e == from_simple_date(y, m, 1) + d - 1`,
    proved for the real encoder in test_epoch_encode_is_linear_in_day.
  * Period components are either the literal 0 or a symbolic Int constrained
    to be non-zero. The Python code branches on Period values only through
    `== 0` tests. z3's BoolRef.__bool__ turns `Int('p') == 0` into a
    structural comparison, which gives False, as a concrete non-zero value
    would. So enumerating the 8 zero/non-zero patterns of (years, months, days)
    covers every path that any concrete Period can take.
"""

import contextlib
from dataclasses import dataclass, field
from typing import Callable, List

import z3
from z3 import And, Int, Not, Solver, is_const, is_int_value, unsat

from datesat.core import Date, Period
from datesat.symbolic_int import (
    alpha_beta_int,
    epoch_days_int,
    hybrid_init_epoch_int,
    hybrid_init_ymd_int,
    simple_int,
)

from . import spec

TIMEOUT_MS = int(__import__("os").environ.get("DATESAT_TV_TIMEOUT_MS", "300000"))

_ENCODING_MODULES = [simple_int, epoch_days_int, alpha_beta_int,
                     hybrid_init_ymd_int, hybrid_init_epoch_int]


# ── Symbolic stand-ins for Python values ────────────────────────────────────

def sym_period(years, months, days) -> Period:
    p = Period.__new__(Period)
    p._years, p._months, p._days = years, months, days
    return p


def sym_date(y, m, d) -> Date:
    dt = Date.__new__(Date)
    dt._year, dt._month, dt._day, dt._bounded = y, m, d, False
    return dt


def _lifted_intval(v, ctx=None):
    return v if z3.is_expr(v) else z3.IntVal(v, ctx)


def _spec_days_since_epoch_from_date(dt):
    return spec.ed_from_simple_date((dt.year, dt.month, dt.day))


_DECODE_FACTS = []
_DECODE_CACHE = {}


def _decode_by_contract(n):
    key = n.get_id()
    if key not in _DECODE_CACHE:
        k = len(_DECODE_CACHE)
        D = tuple(Int(f"dec{k}_{c}") for c in "ymd")
        _DECODE_FACTS.extend([spec.is_valid(*D), spec.ed_from_simple_date(D) == n])
        _DECODE_CACHE[key] = D
    return _DECODE_CACHE[key]


_REF_DATES = []


def sym_ymd(tag):
    """Fresh symbolic reference date (y, m, d); registered so `prove` can add
    injectivity instances relating it to decoder outputs. Call it inside
    `symbolic_mode()`, which resets the registry on entry."""
    D = tuple(Int(f"{c}_{tag}") for c in ("y", "m", "d"))
    _REF_DATES.append(D)
    return D


def _injective(A, B):
    # from_simple_date is injective on valid dates; proved over unbounded
    # integers in test_spec_transcription_lemmas.
    return z3.Implies(And(spec.is_valid(*A), spec.is_valid(*B),
                          spec.ed_from_simple_date(A) == spec.ed_from_simple_date(B)),
                      spec.eq(A, B))


_ENCODE_CACHE = {}


def _encode_by_contract(y, m, d):
    key = tuple(z3.IntVal(0).__add__(t).get_id() if not z3.is_expr(t) else t.get_id() for t in (y, m, d))
    if key not in _ENCODE_CACHE:
        e = Int(f"enc{len(_ENCODE_CACHE)}")
        _DECODE_FACTS.append(z3.Implies(And(1 <= m, m <= 12),
                                        e == spec.ed_from_simple_date((y, m, 1)) + d - 1))
        _ENCODE_CACHE[key] = e
    return _ENCODE_CACHE[key]


def alpha_canonical(A):
    """For 1 <= m <= 12, AlphaBeta alpha is the linear month count
    (cf. lemma_alpha_canonical in alpha_beta.rs). Proved in test_alpha_lemmas."""
    return z3.Implies(And(1 <= A[1], A[1] <= 12),
                      spec.ab_from_simple_date(A)[0] == 12 * A[0] + A[1] - (12 * 2000 + 3))


def add_months_linear(D, n):
    """add_months advances the linear month count by n. Proved in test_alpha_lemmas."""
    AM = spec.add_months(D, n)
    return 12 * AM[0] + AM[1] == 12 * D[0] + D[1] + n


def contract_facts():
    """Contract facts plus instances of lemmas proved elsewhere in this suite,
    added as hypotheses to every query (sound: each one is a valid formula)."""
    facts = list(_DECODE_FACTS)
    decoded = list(_DECODE_CACHE.values())
    others = decoded + _REF_DATES
    for i, A in enumerate(decoded):
        for B in others[i + 1:]:
            facts.append(_injective(A, B))
    facts += [alpha_canonical(A) for A in others]
    return facts


@contextlib.contextmanager
def symbolic_mode():
    _DECODE_FACTS.clear()
    _DECODE_CACHE.clear()
    _REF_DATES.clear()
    _ENCODE_CACHE.clear()
    saved = [(epoch_days_int, "_ymd_from_days_since_epoch_z3", epoch_days_int._ymd_from_days_since_epoch_z3),
             (epoch_days_int, "_days_since_epoch_from_ymd_z3", epoch_days_int._days_since_epoch_from_ymd_z3)]
    epoch_days_int._ymd_from_days_since_epoch_z3 = _decode_by_contract
    epoch_days_int._days_since_epoch_from_ymd_z3 = _encode_by_contract
    for mod in _ENCODING_MODULES:
        for attr, repl in (("IntVal", _lifted_intval),
                           ("days_since_epoch_from_date", _spec_days_since_epoch_from_date)):
            if hasattr(mod, attr):
                saved.append((mod, attr, getattr(mod, attr)))
                setattr(mod, attr, repl)
    try:
        yield
    finally:
        for mod, attr, orig in saved:
            setattr(mod, attr, orig)
        _DECODE_FACTS.clear()
        _DECODE_CACHE.clear()
        _ENCODE_CACHE.clear()
        _REF_DATES.clear()


ZERO_PATTERNS = [(zy, zm, zd) for zy in (True, False) for zm in (True, False) for zd in (True, False)]


def period_for_pattern(pattern, tag=""):
    """Return (Period, (py, pm, pd) as Z3 terms, side conditions) for a zero pattern."""
    comps, conds = [], []
    for name, is_zero in zip(("py", "pm", "pd"), pattern):
        if is_zero:
            comps.append(z3.IntVal(0))
        else:
            v = Int(f"{name}{tag}")
            comps.append(v)
            conds.append(v != 0)
    return sym_period(*comps), tuple(comps), conds


def pattern_id(pattern):
    return "".join("0" if z else c for z, c in zip(pattern, "YMD"))


# ── Proof obligations ───────────────────────────────────────────────────────

class ValidationFailure(AssertionError):
    pass


def prove(claim, hypotheses=(), label="", timeout_ms=TIMEOUT_MS):
    """Assert that `hypotheses => claim` is valid; raise with a counterexample otherwise."""
    s = Solver()
    s.set("timeout", timeout_ms)
    s.add(*hypotheses)
    s.add(*contract_facts())
    s.add(Not(claim))
    r = s.check()
    if r == unsat:
        return
    if r == z3.sat:
        raise ValidationFailure(f"[{label}] counterexample:\n{s.model()}")
    raise ValidationFailure(f"[{label}] solver returned {r} ({s.reason_unknown()})")


def free_constants(terms):
    """Uninterpreted Int constants occurring in `terms`."""
    seen, out, stack = set(), set(), list(terms)
    while stack:
        t = stack.pop()
        if t.get_id() in seen:
            continue
        seen.add(t.get_id())
        if is_const(t) and t.decl().kind() == z3.Z3_OP_UNINTERPRETED:
            out.add(t)
        stack.extend(t.children())
    return out


# ── Encoding adapters ───────────────────────────────────────────────────────
#
# For each encoding we state the Verus congruence relation between a Python
# DateVar and a reference date D = (y, m, d), and a witness: values for the
# DateVar's own Z3 constants that make it represent D. The witness is used for
# the completeness direction (every reference date is representable).

def _is_var(t):
    return t is not None and is_const(t) and not is_int_value(t)


@dataclass
class Encoding:
    name: str
    make_solver: Callable
    congruent: Callable          # (var, D) -> BoolRef
    witness: Callable            # (var, D) -> list[BoolRef]
    supports_symbolic_days: bool = True
    marks: List[str] = field(default_factory=list)

    def new_var(self, solver_obj, name):
        return solver_obj.add_date_var(name)

    def assertions(self, solver_obj):
        return list(solver_obj.solver.assertions())


def _simple_congruent(v, D):
    return And(v.year == D[0], v.month == D[1], v.day == D[2])


def _simple_witness(v, D):
    return [t == x for t, x in zip((v.year, v.month, v.day), D) if _is_var(t)]


def _epoch_congruent(v, D):
    # epoch_delta.rs: ed_congruent(d, ed) <=> ed == EpochDelta::from_ymd(d)
    return v.days_var == spec.ed_from_simple_date(D)


def _epoch_witness(v, D):
    return [v.days_var == spec.ed_from_simple_date(D)] if _is_var(v.days_var) else []


def _ab_congruent(v, D):
    # alpha_beta.rs: ab_congruent(d, ab) <=> ab == AlphaBeta::from_ymd(d)
    a, b = spec.ab_from_simple_date(D)
    return And(v.months_var == a, v.beta_var == b)


def _ab_witness(v, D):
    a, b = spec.ab_from_simple_date(D)
    return [t == x for t, x in ((v.months_var, a), (v.beta_var, b)) if _is_var(t)]


def _hybrid_congruent(v, D):
    # hybrid_ymd.rs: hybrid_congruent(d, h): every representation whose flag
    # is set agrees with d, and at least one flag is set.
    assert v._ymd_consistent or v._epoch_consistent, f"{v.name}: no consistent representation"
    parts = []
    if v._ymd_consistent:
        assert v._ymd_exists
        parts.append(And(v._year_var == D[0], v._month_var == D[1], v._day_var == D[2]))
    if v._epoch_consistent:
        parts.append(v.epoch_var == spec.ed_from_simple_date(D))
    return And(*parts)


def _hybrid_witness(v, D):
    # Every Z3 constant the object owns gets its intended value, whether or
    # not its flag is currently set (lazy links may be asserted later).
    w = []
    if v._ymd_exists:
        w += [t == x for t, x in zip((v._year_var, v._month_var, v._day_var), D) if _is_var(t)]
    if _is_var(v.epoch_var):
        w.append(v.epoch_var == spec.ed_from_simple_date(D))
    return w


ENCODINGS = {
    "simple": Encoding("simple", simple_int.SimpleSolver, _simple_congruent, _simple_witness,
                       supports_symbolic_days=False),
    "epoch_days": Encoding("epoch_days", epoch_days_int.EpochDaysSolver, _epoch_congruent, _epoch_witness),
    "alpha_beta": Encoding("alpha_beta", alpha_beta_int.AlphaBetaSolver, _ab_congruent, _ab_witness),
    "hybrid_init_ymd": Encoding("hybrid_init_ymd", hybrid_init_ymd_int.HybridInitYmdSolver,
                                _hybrid_congruent, _hybrid_witness),
    "hybrid_init_epoch": Encoding("hybrid_init_epoch", hybrid_init_epoch_int.HybridInitEpochSolver,
                                  _hybrid_congruent, _hybrid_witness),
}


def ref_date(tag):
    return sym_ymd(f"r{tag}")


def domain(D):
    """D is a valid date inside the Python-supported year range."""
    return And(spec.is_valid(*D), spec.in_python_range(D))


def check_complete(enc, solver_obj, objs_and_dates, extra_hyps=(), label=""):
    """Completeness: for the intended reference dates, the witness assignment
    satisfies every assertion the Python code added to the solver. So no
    reference behaviour is lost by the encoding's side constraints.
    `objs_and_dates`: list of (DateVar, D)."""
    asserts = enc.assertions(solver_obj)
    witness = []
    for v, D in objs_and_dates:
        witness += enc.witness(v, D)
    covered = free_constants([w.arg(0) for w in witness])
    spec_consts = set()
    for _, D in objs_and_dates:
        spec_consts |= free_constants([z3.IntVal(0) + x for x in D])
    spec_consts |= free_constants(list(extra_hyps))
    # decoder outputs are determined by their (satisfiable) contract facts
    spec_consts |= free_constants(contract_facts())
    uncovered = free_constants(asserts) - covered - spec_consts
    if uncovered:
        raise ValidationFailure(f"[{label}] witness does not cover {sorted(map(str, uncovered))}")
    hyps = [domain(D) for _, D in objs_and_dates] + list(extra_hyps) + witness
    prove(And(*asserts) if asserts else z3.BoolVal(True), hyps, label=f"{label}/complete")
