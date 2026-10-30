# Translation validation of the Python encodings

The Verus proofs in [`proofs/`](../../proofs) show that each *encoding*, written as
Verus spec functions, is equisatisfiable with the reference YMD semantics. They say
nothing about the Python code in `datesat/symbolic_int/`, which is what actually runs.
This directory connects the two without re-implementing anything in Verus.

The Python `DateVar` methods return Z3 terms. So we call them on **symbolic** inputs
and ask Z3 whether those exact terms can ever disagree with a Z3 transcription of the
Verus spec. `unsat` is a proof about the code Python actually generates.

```
pytest tests/translation_validation -n auto          # everything
pytest tests/translation_validation -m translation_validation -k "not differential"
```

The full suite is about 500 checks. Without the hybrid derived-receiver additions it
took roughly 17 minutes on 8 workers; those add 55 queries, many of 1–5 minutes each.
The slowest are the alpha_beta addition queries, at 4–7 minutes each. Every check is
marked `translation_validation`, so `-m "not translation_validation"` skips them.
Env knobs: `DATESAT_TV_TIMEOUT_MS` (per-query Z3 timeout, default 300000),
`DATESAT_TV_RANGE=paper`, `DATESAT_DIFF_CASES`.

To check that the harness has teeth, inject a bug into an encoding (an off-by-one
in `eom_clamp`, a dropped 400-year leap rule, a missing 100-year clamp in the
decoder, a wrong comparison branch in a hybrid). The relevant check then fails
with a concrete counterexample.

| File | Role |
|------|------|
| [`spec.py`](spec.py) | Z3 transcription of `simple_date.rs`, `period.rs`, `epoch_delta.rs`, `alpha_beta.rs` (no `datesat` imports) |
| [`reference_eval.py`](reference_eval.py) | Concrete, literal port of the recursive Verus `add_days` / `add_period` |
| [`harness.py`](harness.py) | Symbolic Period/Date stand-ins, congruence relation and witness per encoding, `prove` |
| [`test_translation_validation.py`](test_translation_validation.py) | The proof obligations (Z3) |
| [`test_differential.py`](test_differential.py) | Random-AST differential tests for the parser / glue (tested, not proved) |

## What is proved (per encoding: simple, epoch_days, alpha_beta, hybrid_init_ymd, hybrid_init_epoch)

These are the Python-level counterparts of the three congruence lemmas the Verus
equisatisfiability proofs are built from (see `proofs/README.md`). The congruence
relation used for each encoding is the Verus one (`ed_congruent`, `ab_congruent`,
`hybrid_congruent`, with the hybrid flags taken from the Python object's
`_ymd_consistent` / `_epoch_consistent`).

1. **Construction.** For a fresh `add_date_var`, every model of the constraints it adds
   is a valid date that the variable is congruent to (sound). Every valid date in years
   1..9999 satisfies those constraints (complete). `.year/.month/.day` return the
   date's components.
2. **Addition.** If `x` is congruent to `D`, then `x + P` is congruent to
   `SimpleDate::add_period(D, P)` and its accessors return that date. This holds for
   all `D` and for all 8 zero/non-zero patterns of `P = (years, months, days)`. The
   Python code branches on a Period only through `== 0` tests, so the 8 patterns
   cover every path a concrete Period can take. For the hybrids the receiver `x` is
   checked in every representation state: fresh, epoch-only (after a day addition),
   YMD-only with expression fields (after a month addition), and both (after a
   comparison materialized the missing side). Exception: 9 of these 64 derived-receiver
   cases, a month-derived receiver plus a period with non-zero months, time out in Z3
   (or finish close to the limit and time out under load) and are marked `xfail(run=False)` (`TIMEOUT_CASES`); they are covered
   only by the differential tests. Completeness also holds: the side
   constraints `__add__` asserts (bounds, hybrid lazy links) are satisfiable for every
   in-range input/result. `x - P` is checked to build the same terms as `x + (-P)`.
3. **Comparison.** For `<, <=, >, >=, ==, !=` between congruent operands
   (variables, literals on either side, and, for the hybrids, operands in every
   representation state: fresh, epoch-only, YMD-only), the Python BoolRef is
   equivalent to `SimpleDate::lt` / `eq`. The hybrids' lazy materialization keeps
   both operands congruent.
4. **Helpers.** `_days_since_epoch_from_ymd_z3 == EpochDelta::from_simple_date` on all
   valid dates (and it is affine in the day, which alpha_beta relies on).
   `_ymd_from_days_since_epoch_z3(n)` is valid and inverts `from_simple_date` for
   **every** integer `n`. The alpha helpers equal `year_of_alpha` / `month_of_alpha`.
   `days_in_month`, `normalize_month` and `eom_clamp` equal `dim` / `add_months`.
5. **Exhaustive (concrete) checks.** `days_since_epoch_from_date` (datetime-based,
   used to embed literals) and `date_from_days_since_epoch` (used to read models) are
   checked against `from_simple_date` for every date from 0001-01-01 to 9999-12-31
   (`DATESAT_TV_RANGE=paper` limits this to 1900-03-01..2100-02-28). The alpha_beta
   model decoder is checked against `AlphaBeta::to_ymd` for every `(alpha, beta)` the
   solver's bounds allow.

Most queries are over unbounded integers. The year range 1..9999 shows up only where
the Python code itself imposes it.

### How the recursive `add_days` is handled

`SimpleDate::add_days` is recursive, so it cannot be a Z3 term. `spec.add_days_rel`
uses the closed-form characterization that the Verus proofs already establish:
`r = d.add_days(n)` iff `r` is valid and `from_simple_date(r) = from_simple_date(d) + n`
(`lemma_date_add_days_preserves_validity`, `lemma_from_simple_date_add_days`, and
injectivity from `theorem_epoch_delta_congruent_preserves_comparison`).
`test_spec_add_period_matches_recursive_verus_spec` cross-checks this against the
literal recursive port in `reference_eval.py` on 2,000 random cases (any start day,
so end-of-month clamping is exercised), as a guard against transcription mistakes.

### Modular steps (each one discharged separately)

* `symbolic_mode` replaces the epoch decoder by its contract (fresh `(y, m, d)` with
  `is_valid` and `from_simple_date(y, m, d) == n`). The contract is proved for the real
  decoder in `test_epoch_decode_is_inverse` and determines the output uniquely.
  Without this step, Z3 has to unfold the nonlinear 400/100/4-year decomposition
  inside every query and times out.
* `symbolic_mode` replaces `days_since_epoch_from_date` (datetime) by its spec. The
  exhaustive check justifies this. It also lifts `IntVal` to pass Z3 terms through,
  which is the identity on values.
* The **simple** encoding adds days by unrolling one loop iteration per day, so `days`
  must be concrete there. The ±1 cases prove the loop body equals `add_days(±1)` on
  every valid date whose input and result are in years 1..9999 (the bounds `__add__`
  asserts), which is all the induction needs. Because the body does not depend on the iteration index and
  `add_days_rel` composes, `k` iterations compute `add_days(k)` for every `k`. That
  induction step is argued on paper, not machine-checked. Day values
  0, ±1, ±2 and +31 are also checked end to end (−31 is left to the induction
  argument because the 31-fold unrolled term times out).

### Is `spec.py` the Verus spec?

`spec.py`, `reference_eval.py` and `_py_fsd` are hand transcriptions. In
[`tests/spec_adequacy/`](../spec_adequacy) they are compared with a compiled,
Verus-verified executable version of the spec (`proofs/src/oracle.rs`). The epoch
formula is compared exhaustively over years 1..9999, and the rest on structured and
random cases. That directory also checks the reference semantics itself against
Python's `datetime` and `java.time`.

## What is *not* covered, stated plainly

* **The parser → generated code → builder glue, and the Int/Bool parts, are tested,
  not proved.** `test_differential.py` generates random well-formed ASTs over the
  Verus grammar, draws an environment first, and asserts each AST or its negation,
  whichever holds there. So every case is satisfiable by construction and each
  encoding must answer `sat` (completeness). Every returned model is then re-evaluated
  with the reference semantics (soundness). Use `DATESAT_DIFF_CASES=N` to run more
  cases. A case where the solver hits its 60 s timeout is skipped, not failed, so
  check the skip count in the pytest summary (`-rs`).
* **Literal + Period is tested, not proved.** `Date + Period` on two literals is
  computed in Python with dateutil's `relativedelta`, not with Z3 terms.
  `test_literal_add_period_matches_spec` compares it (and `Date - Period`) with
  `reference_eval.add_period` on structured and random cases. It agrees whenever the
  result and the years-and-months midpoint are in years 1..9999, and raises otherwise.
* **Bounded domain.** The Verus model is unbounded. The Python solvers restrict every
  date, *including intermediates* such as `x + P`, to years 1..9999 with **global**
  hard constraints, even when the date appears under `!` or `||`. So the
  correspondence is exact only when every date and intermediate stays in range.
  Outside it, Python can report `unsat` where the unbounded semantics would be `sat`.
  Every model Python returns is still correct.
* Composition of the per-operation lemmas into a whole-AST theorem is the structural
  induction in `proofs/src/equivalence.rs`. It is reused informally, not re-checked
  against the Python AST walk.
* Parametric literals such as `Date(x+1, 1, 1)` (rewritten by the parser to
  component-wise comparisons), the router, MaxSAT soft constraints, the bitvector
  implementations and `future_work/` are out of scope.
