# DateSAT Verification

This directory contains machine-checkable proofs of the main theorems in the DateSAT paper. The proofs are written in [Verus](https://github.com/verus-lang/verus), a Rust-based verification tool.

## Running the verifier

First, [install Verus](https://github.com/verus-lang/verus/blob/main/INSTALL.md) (including Rustup and the specific Rust toolchain version that Verus requires; see step 4).

Then, in this directory, run:

```
/path/to/verus src/main.rs
```

If verification succeeds, you will see output like:

```
verification results:: 133 verified, 0 errors
```

## File overview

| File | Purpose |
|------|---------|
| [`src/main.rs`](src/main.rs) | Top-level theorem statements (the main claims) |
| [`src/ast_eval.rs`](src/ast_eval.rs) | AST definition, environment, evaluation semantics, satisfiability |
| [`src/semantics.rs`](src/semantics.rs) | The core semantics (Fig. 3): YMD dates and date-period arithmetic |
| [`src/simple_date.rs`](src/simple_date.rs) | The Simple encoding: a simple baseline encoding used by the Python solver |
| [`src/period.rs`](src/period.rs) | Calendar periods (years, months, days) |
| [`src/epoch_delta.rs`](src/epoch_delta.rs) | The Epoch-Based encoding: days since March 1, 2000 |
| [`src/hybrid_ymd.rs`](src/hybrid_ymd.rs) | The Hybrid encoding (YMD-initial variant): lazy union of YMD and epoch-delta, literals embedded YMD-only |
| [`src/hybrid_epoch.rs`](src/hybrid_epoch.rs) | The Hybrid encoding (epoch-initial variant): same dual representation, but literals embedded epoch-only |
| [`src/alpha_beta.rs`](src/alpha_beta.rs) | The Alpha-Beta encoding: (months-since-epoch, day-offset) |
| [`src/monotonicity.rs`](src/monotonicity.rs) | Proof of monotonicity of date-period addition |
| [`src/equivalence.rs`](src/equivalence.rs) | Equisatisfiability proofs for all encodings |

## Tour of the proofs

### Main claims

The verified theorem statements are in [`src/main.rs`](src/main.rs). The equisatisfiability theorems state that for any well-formed DateSAT constraint, satisfiability under the core semantics (`Date`) is equivalent to satisfiability under each encoding:

```rust
// Theorem 3: SimpleDate equisatisfiability
assert forall|ast: Ast| #![auto]
    ast.is_well_formed() implies
        ast.is_sat::<Date>() == ast.is_sat::<SimpleDate>()
    by { theorem_ast_simple_date_equisat(ast); }

// Theorem 4: EpochDelta equisatisfiability
assert forall|ast: Ast| #![auto]
    ast.is_well_formed() implies
        ast.is_sat::<Date>() == ast.is_sat::<EpochDelta>()
    by { theorem_ast_epoch_delta_equisat(ast); }

// Theorem 5a: Hybrid (YMD-initial) equisatisfiability
assert forall|ast: Ast| #![auto]
    ast.is_well_formed() implies
        ast.is_sat::<Date>() == ast.is_sat::<hybrid_ymd::Hybrid>()
    by { theorem_ast_hybrid_ymd_equisat(ast); }

// Theorem 5b: Hybrid (epoch-initial) equisatisfiability
assert forall|ast: Ast| #![auto]
    ast.is_well_formed() implies
        ast.is_sat::<Date>() == ast.is_sat::<hybrid_epoch::Hybrid>()
    by { theorem_ast_hybrid_epoch_equisat(ast); }

// Theorem 6: AlphaBeta equisatisfiability
assert forall|ast: Ast| #![auto]
    ast.is_well_formed() implies
        ast.is_sat::<Date>() == ast.is_sat::<AlphaBeta>()
    by { theorem_ast_ab_equisat(ast); }
```

### AST and satisfiability

A DateSAT constraint is represented as an `Ast` whose root is a `BoolExpr`. The grammar includes boolean, integer, and date expressions (see [`src/ast_eval.rs`](src/ast_eval.rs)):

```rust
pub struct Ast {
    pub root: BoolExpr,
}

pub enum BoolExpr {
    And(Box<BoolExpr>, Box<BoolExpr>),
    Or(Box<BoolExpr>, Box<BoolExpr>),
    Not(Box<BoolExpr>),
    Implies(Box<BoolExpr>, Box<BoolExpr>),
    Literal(bool),
    Var(Identifier),
    DateLt(Box<DateExpr>, Box<DateExpr>),
    DateEq(Box<DateExpr>, Box<DateExpr>),
    IntLt(Box<IntExpr>, Box<IntExpr>),
    IntEq(Box<IntExpr>, Box<IntExpr>),
}

pub enum DateExpr {
    Literal(int, int, int),
    Var(Identifier),
    Add(Box<DateExpr>, PeriodExpr),
}
```

An `Environment` binds integer, boolean, and date variables:

```rust
pub struct Environment {
    pub int_vars: Map<Identifier, int>,
    pub bool_vars: Map<Identifier, bool>,
    pub date_vars: Map<Identifier, Date>,
}
```

An `Environment` is *properly closed* for an `Ast` (`is_properly_closed`) if it binds every variable that occurs in the AST, and every date variable is bound to a valid date. This ensures that evaluation never looks up an unbound variable or starts from an invalid date.

Satisfiability is defined as the existence of a properly-closed environment under which the AST evaluates to true:

```rust
pub open spec fn is_sat<D: DateEncoding>(self) -> bool {
    exists|env: Environment| #![auto]
        self.is_properly_closed(env) && self.eval::<D>(env) == true
}
```

### Evaluation is generic over encodings

Evaluation is parameterized by a `DateEncoding` trait, defined in [`src/main.rs`](src/main.rs):

```rust
pub trait DateEncoding: Sized {
    spec fn from_ymd(y: int, m: int, d: int) -> Self;
    spec fn year(self) -> int;
    spec fn month(self) -> int;
    spec fn day(self) -> int;
    spec fn lt(self, other: Self) -> bool;
    spec fn eq(self, other: Self) -> bool;
    spec fn add_period(self, period: Period) -> Self;
}
```

Each encoding implements this trait, and `eval` uses it generically. For example, date expression evaluation dispatches through the trait:

```rust
pub open spec fn eval<D: DateEncoding>(self, env: Environment) -> D {
    match self {
        DateExpr::Literal(y, m, d) => D::from_ymd(y, m, d),
        DateExpr::Var(id) => {
            let sd = env.date_vars[id];
            D::from_ymd(sd.year(), sd.month(), sd.day())
        },
        DateExpr::Add(base, period) => {
            base.eval::<D>(env).add_period(period.eval())
        },
    }
}
```

Boolean and integer expressions evaluate similarly, with date comparisons delegated to the encoding's `lt` and `eq` methods.

### Semantics and encodings

The core semantics and every encoding implement the same `DateEncoding` trait; each encoding provides a different internal representation of dates.

**Date** — the core semantics (Fig. 3 of the paper), representing dates directly as (year, month, day) triples. See [`src/semantics.rs`](src/semantics.rs).

```rust
pub struct Date { year: int, month: int, day: int }
```

**SimpleDate** — a simple baseline encoding used by the Python solver, representing dates as (year, month, day) triples and adding days one at a time. See [`src/simple_date.rs`](src/simple_date.rs).

```rust
pub struct SimpleDate { year: int, month: int, day: int }
```

**EpochDelta** — represents a date as the number of days since March 1, 2000. See [`src/epoch_delta.rs`](src/epoch_delta.rs).

```rust
pub struct EpochDelta { delta: int }
```

**Hybrid** — a lazy union that can hold a YMD form, an epoch-delta form, or both. There are two variants with the same `Hybrid` struct, which differ only in how literals are embedded (`from_ymd`): [`src/hybrid_ymd.rs`](src/hybrid_ymd.rs) embeds them as YMD only, while [`src/hybrid_epoch.rs`](src/hybrid_epoch.rs) embeds them as an epoch delta only. The missing form is computed lazily on first use.

```rust
pub struct Hybrid { year: int, month: int, day: int, delta: int, ymd: bool, epoch: bool }
```

**AlphaBeta** — represents a date as (alpha, beta) where alpha is months elapsed since the epoch and beta is the 0-indexed day offset within the month. See [`src/alpha_beta.rs`](src/alpha_beta.rs).

```rust
pub struct AlphaBeta { alpha: int, beta: int }
```

### Congruence: the key proof concept

The central idea in the equisatisfiability proofs is **congruence**: a relation between a `Date` value (the semantics) and an encoded value asserting that they represent the same calendar date — i.e., that they agree on year, month, and day. Concretely, the encoded value must be exactly what `from_ymd` produces for the date (for valid dates, this is the same as agreeing on year, month, and day). For example, for SimpleDate and EpochDelta:

```rust
pub open spec fn sd_congruent(d: Date, sd: SimpleDate) -> bool {
    sd == SimpleDate::from_ymd(d.year(), d.month(), d.day())
}
```

```rust
pub open spec fn ed_congruent(d: Date, ed: EpochDelta) -> bool {
    ed == EpochDelta::from_ymd(d.year(), d.month(), d.day())
}
```

And for AlphaBeta:

```rust
pub open spec fn ab_congruent(d: Date, ab: AlphaBeta) -> bool {
    ab == AlphaBeta::from_ymd(d.year(), d.month(), d.day())
}
```
Three properties of congruence are established for each encoding:

1. **Construction**: `from_ymd` produces congruent values (the base case).
2. **Preservation under addition**: adding the same period to congruent values yields congruent results (the inductive step, which relies on Theorem 1).
3. **Preservation of comparisons**: congruent pairs agree on ordering and equality (the bridge to boolean evaluation).

These three properties suffice to propagate evaluation equivalence through the entire AST by structural induction, yielding equisatisfiability.
