# Hybrid encoding, worked examples: `hybrid_init_ymd` vs `hybrid_init_epoch`

The two hybrid variants share all of their operation code (`__add__`, the
comparison operators, the lazy `_epoch_expr()` / `_ymd_expr()` derivers). The
**only** difference between them is the representation a fresh user variable
*starts in*:

- `hybrid_init_ymd` — a user var starts with **Y/M/D** as the source of truth
  (`y`, `m`, `d` materialized and bounded); the epoch side is derived on demand.
- `hybrid_init_epoch` — a user var starts with **epoch days** as the source of truth
  (`epoch` materialized and bounded); the Y/M/D side is derived on demand.

The starting representation is not a startup cost — declaring the Z3 integers is
free. It matters because it decides, for each later operation, whether that
operation runs **with no format conversion** or has to pay a conversion to the
other side.

## The two conversions

Every conversion in the examples below is one of these two:

- **conversion: Y/M/D → epoch** — compute `epoch = days_since_epoch_from_ymd(y, m, d)`
  and assert the link `x_epoch == …`. Needed when a variable currently held as
  Y/M/D must be used in epoch form (day arithmetic, an epoch comparison).
- **conversion: epoch → Y/M/D** — compute `y, m, d = ymd_from_days_since_epoch(epoch)`,
  create the `x_year / x_month / x_day` integers, and assert the three linking
  equalities. Needed when a variable currently held as epoch must expose its
  components (`.year` / `.month` / `.day`, month/year arithmetic).

When no conversion is noted, the representation the operation needs is already
the source of truth, so the operation is **free** (no conversion).

---

## Example 1 — component access + month/year arithmetic (Y/M/D-native)

```
a, b : Date
a.month == 4
b == a + Period(2, 3, 0)
b.year == 2028
```

### `hybrid_init_ymd`

```python
a, b : Date
# a,b START in Y/M/D: a_year/month/day, b_year/month/day created + bounded
# epoch side deferred (a_epoch/b_epoch exist but are left unconstrained)

a.month == 4
# a.month: a is Y/M/D already -> returns a_month directly.  NO CONVERSION.

b == a + Period(2,3,0)
# +Period(2,3,0): months/years, days=0 -> general path
# reads a's Y/M/D: a is Y/M/D already -> reuse a_year/month/day.  NO CONVERSION.
# compute y1,m1 (normalize months), d1 (EOM clamp) as symbolic Y/M/D exprs
# result is marked Y/M/D-consistent, epoch side LAZY: no link emitted (hybrid_init_ymd_int.py:500-510)
# b == result: b is Y/M/D, result is Y/M/D -> component equality.  NO CONVERSION.

b.year == 2028
# b.year: b is Y/M/D already -> returns b_year directly.  NO CONVERSION.
```

**Total conversions: 0, and no epoch formula is emitted at all.** `a_epoch`,
`b_epoch`, and `result_epoch` stay unconstrained free integers — nothing ever
reads them, so the epoch link is never asserted. (In `hybrid_both` this same
`b == a + Period(2,3,0)` *would* eagerly emit `result_epoch == days_since_epoch_from_ymd(y1,m1,d1)`;
that eager link is exactly the trade `hybrid_both` makes.)

### `hybrid_init_epoch`

```python
a, b : Date
# a,b START in epoch: a_epoch, b_epoch created + range-bounded; no Y/M/D vars yet

a.month == 4
# a.month: a is epoch, needs components ->
#   CONVERSION: epoch -> Y/M/D for a
#     (create a_year/month/day, link a_epoch==days_since_epoch_from_ymd(...),
#      assert them from ymd_from_days_since_epoch(a_epoch)).  a now holds both.

b == a + Period(2,3,0)
# general path; reads a's Y/M/D: a now has Y/M/D (from line above) -> reuse.  NO CONVERSION.
# result is Y/M/D-only (lazy, no epoch link)
# b == result: b is epoch-only, result is Y/M/D-only -> MISMATCH, reconcile on epoch:
#   CONVERSION: Y/M/D -> epoch for result  (assert result_epoch==days_since_epoch_from_ymd(y1,m1,d1))
#   CONVERSION: epoch -> Y/M/D for b        (create b_year/month/day + assert from ymd(b_epoch))

b.year == 2028
# b.year: b now has Y/M/D (converted at the equality above) -> reuse.  NO CONVERSION.
```

**Total conversions: 3** (epoch → Y/M/D for `a`; then Y/M/D → epoch for `result`
*and* epoch → Y/M/D for `b` to reconcile the equality). Starting in epoch forces
a conversion on every component touch and a reconciliation at the equality —
worse fit here.

---

## Example 2 — day arithmetic + comparison (epoch-native)

```
a, b : Date
b == a + Period(0, 0, 100)
a < b
```

### `hybrid_init_ymd`

```python
a, b : Date
# a,b START in Y/M/D; epoch side deferred

b == a + Period(0,0,100)
# +Period(0,0,100): days-only FAST PATH -> result.epoch = (a in epoch) + 100
# a needs epoch but is Y/M/D ->
#   CONVERSION: Y/M/D -> epoch for a  (assert a_epoch==days_since_epoch_from_ymd(a_y,a_m,a_d))
# result.epoch = a_epoch + 100   (result is epoch-only)
# b == result: b is Y/M/D-only, result is epoch-only -> MISMATCH, reconcile on epoch:
#   CONVERSION: Y/M/D -> epoch for b        (assert b_epoch==days_since_epoch_from_ymd(b_y,b_m,b_d))
#   CONVERSION: epoch -> Y/M/D for result   (dead: result's Y/M/D never read below)

a < b
# Not(a >= b): a and b are both epoch now -> epoch comparison.  NO CONVERSION.
```

**Total conversions: 3** (Y/M/D → epoch for `a`, Y/M/D → epoch for `b`, plus one
dead epoch → Y/M/D on the intermediate). Y/M/D start pays to reach epoch
everywhere — worse fit here.

### `hybrid_init_epoch`

```python
a, b : Date
# a,b START in epoch

b == a + Period(0,0,100)
# days-only fast path -> result.epoch = (a in epoch) + 100
# a is epoch already -> use a_epoch.  NO CONVERSION.
# result.epoch = a_epoch + 100   (result is epoch-only)
# b == result: b is epoch, result is epoch -> epoch equality.  NO CONVERSION.

a < b
# Not(a >= b): both epoch -> epoch comparison.  NO CONVERSION.
```

**Total conversions: 0.** Perfect fit.

---

## Example 3 — mixed chain of adds + comparison

```
a, b : Date
b == a + Period(0,0,10) + Period(0,1,0) + Period(0,0,20)
      + Period(2,0,0) + Period(0,0,30) + Period(0,3,0)
a < b
```

The chain is left-associative:
`((((((a+P1)+P2)+P3)+P4)+P5)+P6)`, producing intermediates `r1 … r6`.

- A **day add** (`P1=+10d`, `P3=+20d`, `P5=+30d`) wants its operand in **epoch**
  and produces an **epoch-only** result.
- A **month/year add** (`P2=+1mo`, `P4=+2y`, `P6=+3mo`) wants its operand in
  **Y/M/D** and produces a **Y/M/D-only** result (lazy — no epoch link).

Because the adds alternate day / month / day / month …, and each lazy result is
materialized in only *one* representation, **every add finds its operand in the
wrong representation and must convert it.** The chain ping-pongs. Both variants
pay this; they differ only in *phase* — `hybrid_init_ymd` eats one extra conversion at
the first add (converting `a`), while `hybrid_init_epoch` eats one extra pair at the
final `b == r6` equality. (Contrast `hybrid_both` below, where the eager link
breaks the ping-pong.)

### `hybrid_init_ymd`

```python
a, b : Date
# a,b START in Y/M/D

b == a + Period(0,0,10) + Period(0,1,0) + Period(0,0,20)
      + Period(2,0,0) + Period(0,0,30) + Period(0,3,0)
# r1 = a + 10d  (day add, wants epoch): a is Y/M/D ->
#   CONVERSION: Y/M/D -> epoch for a ;        r1 = epoch-only
# r2 = r1 + 1mo (month add, wants Y/M/D): r1 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r1 ;       r2 = Y/M/D-only (lazy, no link)
# r3 = r2 + 20d (day add): r2 Y/M/D-only ->
#   CONVERSION: Y/M/D -> epoch for r2 ;       r3 = epoch-only
# r4 = r3 + 2y  (month add): r3 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r3 ;       r4 = Y/M/D-only
# r5 = r4 + 30d (day add): r4 Y/M/D-only ->
#   CONVERSION: Y/M/D -> epoch for r4 ;       r5 = epoch-only
# r6 = r5 + 3mo (month add): r5 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r5 ;       r6 = Y/M/D-only
# b == r6: b is Y/M/D-only, r6 is Y/M/D-only -> component equality.  NO CONVERSION.

a < b
# Not(a >= b): a is Y/M/D (also epoch, from the r1 step), b is Y/M/D-only ->
#   Y/M/D LEXICOGRAPHIC comparison.  NO CONVERSION,
#   but the formula is the heavier Or(y>.., And(y==.., Or(m>.., ...))) nest.
```

**Total conversions: 6** — one per add (`a`, `r1`, `r2`, `r3`, `r4`, `r5`). The
final `b == r6` and `a < b` are free (both sides already Y/M/D).

### `hybrid_init_epoch`

```python
a, b : Date
# a,b START in epoch

b == a + Period(0,0,10) + Period(0,1,0) + Period(0,0,20)
      + Period(2,0,0) + Period(0,0,30) + Period(0,3,0)
# r1 = a + 10d  (day add, wants epoch): a is epoch -> NO CONVERSION ;  r1 = epoch-only
# r2 = r1 + 1mo (month add, wants Y/M/D): r1 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r1 ;       r2 = Y/M/D-only (lazy, no link)
# r3 = r2 + 20d (day add): r2 Y/M/D-only ->
#   CONVERSION: Y/M/D -> epoch for r2 ;       r3 = epoch-only
# r4 = r3 + 2y  (month add): r3 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r3 ;       r4 = Y/M/D-only
# r5 = r4 + 30d (day add): r4 Y/M/D-only ->
#   CONVERSION: Y/M/D -> epoch for r4 ;       r5 = epoch-only
# r6 = r5 + 3mo (month add): r5 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r5 ;       r6 = Y/M/D-only
# b == r6: b is epoch-only, r6 is Y/M/D-only -> MISMATCH, reconcile on epoch:
#   CONVERSION: Y/M/D -> epoch for r6 ;  CONVERSION: epoch -> Y/M/D for b

a < b
# Not(a >= b): a epoch-only, b now epoch (converted above) -> epoch comparison.  NO CONVERSION.
```

**Total conversions: 7** — five along the chain (`r1`…`r5`) plus two at the
`b == r6` equality (reconcile `r6` and `b`). The final `a < b` is one integer
inequality.

### `hybrid_both` (why the eager link matters)

`hybrid_both` keeps the question's eager link: the `od==0` month/year add emits
`result_epoch == days_since_epoch_from_ymd(y1,m1,d1)` on the spot, so that result
is consistent in **both** representations at once. That breaks the ping-pong,
because a following day add finds the epoch side already live:

```python
a, b : Date
# a,b START with BOTH sides live (Y/M/D + linked epoch)

b == a + Period(0,0,10) + Period(0,1,0) + Period(0,0,20)
      + Period(2,0,0) + Period(0,0,30) + Period(0,3,0)
# r1 = a + 10d  (day add): a has epoch -> NO CONVERSION ;  r1 = epoch-only
# r2 = r1 + 1mo (month add): r1 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r1 ;  r2 = BOTH (eager link emitted)
# r3 = r2 + 20d (day add): r2 has epoch (eager link) -> NO CONVERSION ;  r3 = epoch-only
# r4 = r3 + 2y  (month add): r3 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r3 ;  r4 = BOTH
# r5 = r4 + 30d (day add): r4 has epoch -> NO CONVERSION ;  r5 = epoch-only
# r6 = r5 + 3mo (month add): r5 epoch-only ->
#   CONVERSION: epoch -> Y/M/D for r5 ;  r6 = BOTH
# b == r6: b has epoch, r6 has epoch -> epoch equality.  NO CONVERSION.

a < b
# both have epoch -> epoch comparison.  NO CONVERSION.
```

**Total conversions: 3** (`r1`, `r3`, `r5` → Y/M/D). The eager links on `r2`,
`r4`, `r6` cost three extra formulas up front but remove the three back-conversions
and the equality reconciliation — so on this mixed chain `hybrid_both` (3) beats
both lazy variants (6 and 7). On Example 1, though, those same eager links are pure
waste. That is the whole trade, and the direct answer to "why the link": the lazy
variants omit it to stay cheap on single-representation problems; `hybrid_both`
pays it always to stay cheap on representation-alternating ones.

---

## Takeaway

- **Example 1** is Y/M/D-native → `hybrid_init_ymd` runs with **0 conversions** (and emits no epoch formula at all), `hybrid_init_epoch` pays **3** (epoch → Y/M/D for `a` and `b`, plus a Y/M/D → epoch to reconcile the equality).
- **Example 2** is epoch-native → `hybrid_init_epoch` runs with **0 conversions**, `hybrid_init_ymd` pays **3** (Y/M/D → epoch for `a` and `b`, plus a reconciling conversion).
- **Example 3** is a representation-alternating chain, so the two lazy variants **ping-pong**: because each lazy intermediate is materialized in only one representation, nearly every add converts its operand. `hybrid_init_ymd` pays **6**, `hybrid_init_epoch` pays **7**, differing only in phase. `hybrid_both` pays only **3**, because its eager links keep both sides live and break the ping-pong — the trade is three wasted formulas on single-representation problems like Example 1.

The headline — *some constraints go faster starting in Y/M/D, some starting in
epoch* — is exactly right. The mechanism underneath it is: the starting
representation decides which operations are free and which pay a
**Y/M/D → epoch** or **epoch → Y/M/D** conversion, and the variant that starts in
the representation the dominant operations prefer emits fewer (and simpler)
formulas to Z3.
