# Differential tests

[`test_differential.py`](test_differential.py) tests every encoding (`simple`,
`epoch_days`, `alpha_beta`, `hybrid_init_ymd`, `hybrid_init_epoch`) end to end, from the
constraint parser through the generated Z3 terms, including the Int/Bool parts.

Random well-formed ASTs over the Verus grammar (`proofs/src/ast_eval.rs`) are rendered
to DateSAT constraint strings. For each one, an environment is drawn first and the AST
or its negation, whichever holds there, is asserted, so every case is satisfiable by
construction:

* **Completeness:** every encoding must answer `sat`.
* **Soundness:** every returned model is re-evaluated with
  [`reference_eval.py`](reference_eval.py), a literal Python port of the Verus
  reference semantics (`proofs/src/simple_date.rs`). `reference_eval.py` is itself
  checked against the compiled Verus oracle in
  [`tests/semantics_vs_libraries/`](../semantics_vs_libraries).

```
pytest -m differential
DATESAT_DIFF_CASES=500 pytest -m differential   # more cases (default 25 per encoding)
```

A case where the solver hits its 60 s timeout is skipped, not failed, so check the
skip count in the pytest summary (`-rs`). Every test is marked `differential`.
