# Lean 4 Date Semantic Oracle

A Lean 4 executable reference oracle for the `Dates.smt2` theory.

| File | Purpose |
|---|---|
| `DateSemantic.lean` | Core implementation — `Date` structure, all constructors, selectors, arithmetic, and comparisons |
| `DateSemanticTests.lean` | `#eval` test cases; imports `DateSemantic` |
| `lakefile.lean` | Lake project definition; registers both libraries |
| `lean-toolchain` | Pins the Lean version (`v4.28.0`); elan reads this automatically |

---

## Step 1 — Install elan and the Lean toolchain

elan is Lean's version manager (like rustup for Rust). You need both elan
**and** a Lean toolchain — installing elan alone is not enough.

```bash
# Install elan
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh

# Reload your shell so elan is on PATH
source ~/.elan/env

# Install the Lean toolchain pinned by lean-toolchain
elan toolchain install leanprover/lean4:v4.28.0
elan default leanprover/lean4:v4.28.0

# Verify — both should print a version immediately
lean --version
lake --version
```

---

## Step 2 — Build and run the tests

All commands below are run from the **`lean/`** directory.
`lake build` must complete before `lake env lean` can resolve the import.

```bash
cd lean/
lake build
lake env lean DateSemanticTests.lean
```

Each `#eval` line prints its result to stdout. Compare against the
`-- expected:` comment on the same line.

To check the implementation file on its own (no cross-file imports):

```bash
lean DateSemantic.lean
```

---

## What the tests check

| Group | What is tested |
|---|---|
| Selector axioms | `dateYear/Month/Day` on valid constructor triples |
| Calendar helpers | `isLeapYear`, `daysInMonth` (internal functions) |
| `dateAdd` — EOM clamp | Jan 31 + 1 month in leap vs non-leap year |
| `dateAdd` — day carry | Forward (Jan 31 + 1d), backward (Mar 1 − 1d), year boundary |
| `dateAdd` — month normalization | Adding 12 months, negative month offset |
| `dateSub` | Reduces to `dateAdd` with negated offsets |
| Comparisons | `dateLt`, `dateLe`, `dateGt`, `dateGe`, reflexivity |
| Equality | Built-in `==`; no separate `date.eq` |
