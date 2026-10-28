"""
Differential tests for the part translation validation does not cover: the
parser -> generated builder code -> DateVar composition, plus the Bool/Int glue.

This part is *tested, not proved*. Random well-formed ASTs over the Verus
grammar (proofs/src/ast_eval.rs) are rendered to DateSAT constraint strings and
evaluated by a literal port of the Verus semantics (reference_eval.py).

  * completeness: we draw an environment first and assert the AST or its
    negation, whichever holds there, so the constraint set is satisfiable by
    construction. Every encoding must answer sat.
  * soundness: every model returned is checked with the reference evaluator.

Set DATESAT_DIFF_CASES to run more cases (default 25 per encoding).
"""

import os
import random

import pytest

import datesat

from . import reference_eval as ref

pytestmark = pytest.mark.translation_validation

APPROACHES = ["simple", "epoch_days", "alpha_beta", "hybrid_init_ymd", "hybrid_init_epoch"]
N_CASES = int(os.environ.get("DATESAT_DIFF_CASES", "25"))
DATE_VARS, INT_VARS, BOOL_VARS = ["x", "y"], ["n"], ["b"]


# ── Random AST generation (mirrors BoolExpr / IntExpr / DateExpr / PeriodExpr) ─

def rand_date(rng):
    y, m = rng.randint(1950, 2050), rng.randint(1, 12)
    return (y, m, rng.randint(1, ref.dim(y, m)))


def gen_period(rng, depth):
    r = rng.random()
    if depth > 0 and r < 0.15:
        return ("padd", gen_period(rng, depth - 1), gen_period(rng, depth - 1))
    if depth > 0 and r < 0.25:
        return ("pscale", gen_period(rng, depth - 1), rng.randint(-3, 3))
    comps = [rng.choice([0, 0, rng.randint(-3, 3)]),
             rng.choice([0, 0, rng.randint(-14, 14)]),
             rng.choice([0, 0, rng.randint(-62, 62)])]
    return ("plit", *comps)


def gen_date(rng, depth):
    r = rng.random()
    if depth > 0 and r < 0.4:
        return ("dadd", gen_date(rng, depth - 1), gen_period(rng, 1), rng.random() < 0.3)
    if r < 0.7:
        return ("dvar", rng.choice(DATE_VARS))
    return ("dlit", *rand_date(rng))


def gen_int(rng, depth):
    r = rng.random()
    if depth > 0 and r < 0.35:
        return (rng.choice(["iadd", "isub"]), gen_int(rng, depth - 1), gen_int(rng, depth - 1))
    if depth > 0 and r < 0.45:
        return ("imul", gen_int(rng, depth - 1), rng.randint(-3, 3))
    if r < 0.75:
        return ("ifield", rng.choice(["year", "month", "day"]), gen_date(rng, depth - 1))
    if r < 0.88:
        return ("ivar", rng.choice(INT_VARS))
    return ("ilit", rng.randint(-5, 2100))


CMP_OPS = ["<", "<=", ">", ">=", "==", "!="]


def gen_bool(rng, depth):
    r = rng.random()
    if depth > 0 and r < 0.35:
        return (rng.choice(["and", "or", "implies"]), gen_bool(rng, depth - 1), gen_bool(rng, depth - 1))
    if depth > 0 and r < 0.45:
        return ("not", gen_bool(rng, depth - 1))
    if r < 0.75:
        return ("dcmp", rng.choice(CMP_OPS), gen_date(rng, 2), gen_date(rng, 2))
    if r < 0.92:
        return ("icmp", rng.choice(CMP_OPS), gen_int(rng, 2), gen_int(rng, 2))
    return ("bvar", rng.choice(BOOL_VARS)) if rng.random() < 0.7 else ("blit", rng.random() < 0.5)


# ── Rendering to the DateSAT surface syntax ─────────────────────────────────

def render(e):
    t = e[0]
    if t == "plit":
        return f"Period({e[1]}, {e[2]}, {e[3]})"
    if t == "padd":
        return f"({render(e[1])} + {render(e[2])})"
    if t == "pscale":
        return f"({e[2]} * {render(e[1])})"
    if t == "dvar" or t == "ivar" or t == "bvar":
        return e[1]
    if t == "dlit":
        return f"Date({e[1]}, {e[2]}, {e[3]})"
    if t == "dadd":
        base, p, as_sub = e[1], e[2], e[3]
        if as_sub:  # x - P is sugar for x + (-1 * P)
            return f"({render(base)} - {render(('pscale', p, -1))})"
        return f"({render(base)} + {render(p)})"
    if t == "ilit":
        return str(e[1]) if e[1] >= 0 else f"({e[1]})"
    if t in ("iadd", "isub"):
        return f"({render(e[1])} {'+' if t == 'iadd' else '-'} {render(e[2])})"
    if t == "imul":
        return f"({e[2]} * {render(e[1])})"
    if t == "ifield":
        return f"({render(e[2])}).{e[1]}"
    if t == "blit":
        return "True" if e[1] else "False"
    if t in ("and", "or", "implies"):
        op = {"and": "&&", "or": "||", "implies": "->"}[t]
        return f"({render(e[1])} {op} {render(e[2])})"
    if t == "not":
        return f"!({render(e[1])})"
    if t in ("dcmp", "icmp"):
        return f"({render(e[2])} {e[1]} {render(e[3])})"
    raise ValueError(t)


# ── Reference evaluation (ast_eval.rs with SimpleDate) ──────────────────────

class OutOfRange(Exception):
    """An intermediate date left years 1..9999, where the Python solvers add
    hard bounds; such cases are outside the validated domain."""


def ev(e, env):
    t = e[0]
    if t == "plit":
        return (e[1], e[2], e[3])
    if t == "padd":
        a, b = ev(e[1], env), ev(e[2], env)
        return tuple(i + j for i, j in zip(a, b))
    if t == "pscale":
        return tuple(i * e[2] for i in ev(e[1], env))
    if t in ("dvar", "ivar", "bvar"):
        return env[e[1]]
    if t == "dlit":
        return (e[1], e[2], e[3])
    if t == "dadd":
        # rendered as `base - (-1 * P)` when e[3], which still means base + P
        p = ev(e[2], env)
        r = ref.add_period(ev(e[1], env), p)
        if not 1 <= r[0] <= 9999:
            raise OutOfRange
        return r
    if t == "ilit":
        return e[1]
    if t == "iadd":
        return ev(e[1], env) + ev(e[2], env)
    if t == "isub":
        return ev(e[1], env) - ev(e[2], env)
    if t == "imul":
        return ev(e[1], env) * e[2]
    if t == "ifield":
        return ev(e[2], env)[["year", "month", "day"].index(e[1])]
    if t == "blit":
        return e[1]
    if t == "and":
        return ev(e[1], env) and ev(e[2], env)
    if t == "or":
        return ev(e[1], env) or ev(e[2], env)
    if t == "implies":
        return (not ev(e[1], env)) or ev(e[2], env)
    if t == "not":
        return not ev(e[1], env)
    if t in ("dcmp", "icmp"):
        a, b = ev(e[2], env), ev(e[3], env)
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[e[1]]
    raise ValueError(t)


def eval_all(asts, env):
    # Evaluate every node strictly (no short-circuit) so OutOfRange anywhere is seen,
    # matching the Python solvers, which bound every intermediate globally.
    def walk(e):
        if isinstance(e, tuple):
            for c in e[1:]:
                walk(c)
            if e[0] in ("dadd",):
                ev(e, env)
    for a in asts:
        walk(a)
    return [ev(a, env) for a in asts]


# ── The tests ───────────────────────────────────────────────────────────────

def _make_case(seed):
    rng = random.Random(seed)
    for _ in range(100):
        env = {v: rand_date(rng) for v in DATE_VARS}
        env.update({v: rng.randint(-50, 2100) for v in INT_VARS})
        env.update({v: rng.random() < 0.5 for v in BOOL_VARS})
        asts = [gen_bool(rng, 2) for _ in range(rng.randint(1, 3))]
        # Pin some variables so the problems stay small; the rest stay free.
        pins = [("dcmp", "==", ("dvar", v), ("dlit", *env[v])) for v in DATE_VARS if rng.random() < 0.4]
        try:
            vals = eval_all(asts, env)
        except OutOfRange:
            continue
        asts = [a if v else ("not", a) for a, v in zip(asts, vals)] + pins
        return env, asts
    pytest.skip("could not draw an in-range case")


def _model_env(result):
    env = {k: (d.year, d.month, d.day) for k, d in result.get("dates", {}).items()}
    env.update(result.get("ints", {}))
    env.update(result.get("bools", {}))
    return env


@pytest.mark.parametrize("approach", APPROACHES)
@pytest.mark.parametrize("seed", range(N_CASES))
def test_differential_against_reference(approach, seed):
    env, asts = _make_case(seed)
    problem = {
        "declarations": [f"{v}: date" for v in DATE_VARS] + [f"{v}: int" for v in INT_VARS]
                        + [f"{v}: bool" for v in BOOL_VARS],
        "constraints": [render(a) for a in asts],
    }
    res = datesat.solve(problem, approach=approach, timeout_ms=60_000, verbose=False)
    if res["status"] == "timeout":
        pytest.skip("solver timeout")
    # completeness: `env` satisfies every constraint under the reference semantics
    assert res["status"] == "sat", f"{approach} says unsat, but reference env {env} satisfies {problem}"
    # soundness: the returned model satisfies every constraint under the reference semantics
    # variables the solver leaves out are unconstrained; any value will do
    defaults = {**{v: (2000, 1, 1) for v in DATE_VARS}, **{v: 0 for v in INT_VARS},
                **{v: False for v in BOOL_VARS}}
    model = {**defaults, **_model_env(res)}
    try:
        vals = eval_all(asts, model)
    except OutOfRange:
        pytest.fail(f"{approach} model {model} drives an intermediate date out of range: {problem}")
    bad = [problem["constraints"][i] for i, v in enumerate(vals) if not v]
    assert not bad, f"{approach} model {model} violates {bad}"
