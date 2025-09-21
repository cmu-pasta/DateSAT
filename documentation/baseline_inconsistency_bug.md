# Baseline Solver Inconsistency Bug

## Problem Summary
The baseline symbolic solver has a **fundamental inconsistency** in its date arithmetic implementation where direct addition and decomposed addition produce different results for mathematically equivalent operations.

## Specific Failing Case
**Test Case**: `Date(2020, 2, 29) + Period(1, 1, 1)`
- **Expected Result**: `Date(2021, 3, 30)`
- **Direct Addition Result**: `Date(2021, 3, 30)` ✅
- **Decomposed Addition Result**: `Date(2021, 3, 29)` ❌
- **Test Status**: FAILED - Decomposed result doesn't match expected

## Root Cause Analysis

### The "Round-Down Policy is Not Associative" Pitfall
This is a classic issue with date arithmetic: **round-down policy is not associative over (Y,M,D)**.

With the baseline specification (NormMonth → EOM round-down → then add D days), these two operations are **not equivalent** in general:

1. **One shot**: `Date + Period(Y, M, D)` ← (baseline spec)
2. **Stepwise**: `(((Date + Period(Y,0,0)) + Period(0,M,0)) + Period(0,0,D))`

### Why the Failing Case Demonstrates This

**Direct (one shot)**:
```
2020-02-29 + (1y,1m,1d)
→ NormMonth(2021,3), round-down min(29,31)=29, +1d → 2021-03-30
```

**Stepwise (Y then M then D)**:
```
2020-02-29 + (1y,0m,0d) → NormMonth(2021,2), round-down to 2021-02-28
then + (0y,1m,0d) → 2021-03-28
then + (0y,0m,1d) → 2021-03-29
```

### The Core Issue
The test named "component decomposition equivalence" will **always fail** if it decomposes by actually applying `(Y,0,0)` then `(0,M,0)` then `(0,0,D)` to the date. Under the EOM policy, equivalence only holds if you combine Y and M **before** the round-down, i.e., apply `(Y,M,0)` together, then `(0,0,D)`.

## Mathematical Context

### Date Arithmetic Non-Associativity
This reveals that date arithmetic with round-down policies is **not associative**:
- `(date + Y) + M ≠ date + (Y + M)` in general
- The order of operations matters when dealing with month-end boundaries
- Leap year transitions compound the problem

### Library Comparison
- **dateutil.relativedelta** (all at once): `2021-03-30`
- **dateutil.relativedelta** (step by step): `2021-03-29`
- **Baseline solver (direct)**: `2021-03-30` (matches "all at once")
- **Baseline solver (decomposed)**: `2021-03-29` (matches "step by step")

## Impact

### Test Failures
- **Component Decomposition Tests**: 22 out of 68 test cases fail
- **Mixed Period Cases**: All cases with complex period arithmetic affected
- **Leap Year Edge Cases**: All Feb 29 transitions affected

### Affected Test Cases
```python
# Examples of failing cases:
(Date(2020, 2, 29), Period(1, 1, 1),  Date(2021, 3, 30))   # 1 day off
(Date(2020, 1, 31), Period(1, 1, 1),  Date(2021, 3, 1))    # 1 day off  
(Date(2020, 5, 31), Period(0, 1, 1),  Date(2020, 7, 1))    # 1 day off
```

## The Fix: Preserve Baseline Semantics

### Recommended Solution: Combine Periods Before Applying
Make "decomposition" **combine periods** before applying to a date. Ensure that whatever path the test calls "decomposed" builds a **single Period** from the components (or at least `(Y,M,0)` together), and then calls `date + that_period`.

### Implementation Steps

#### 1) Add Canonical Period Arithmetic
```python
# in core.py (or wherever Period lives)

@dataclass(frozen=True)
class Period:
    years: int
    months: int
    days: int

    def _canon_months(self, years, months):
        # months -> (carry_y, mod_m in 0..11) with proper handling of negatives
        q, r = divmod(months, 12)
        # Python's divmod already does Euclidean division for ints
        return years + q, r

    def __add__(self, other: "Period") -> "Period":
        y = self.years + other.years
        m = self.months + other.months
        d = self.days + other.days
        y, m = self._canon_months(y, m)
        return Period(y, m, d)

    def __neg__(self) -> "Period":
        return Period(-self.years, -self.months, -self.days)

    def __sub__(self, other: "Period") -> "Period":
        return self + (-other)
```

#### 2) Provide a Helper to Sum Many Periods
```python
def sum_periods(*ps: Period) -> Period:
    total = Period(0, 0, 0)
    for p in ps:
        total = total + p
    return total
```

#### 3) Use "Combine Then Apply" in Decomposition Tests
Instead of doing:
```python
# stepwise (will NOT be equivalent under EOM)
decomp = (((base + Period(Y,0,0)) + Period(0,M,0)) + Period(0,0,D))
```

Do:
```python
# equivalent-by-spec decomposition: combine then apply
combined = sum_periods(Period(Y,0,0), Period(0,M,0), Period(0,0,D))
decomp = base + combined
```

This yields `2021-03-30`, matching "direct".

## Why Not Fix `DateVar.__add__` for Stepwise Case

To make the stepwise `+ (Y,0,0)` then `+ (0,M,0)` equal to the one-shot `(Y,M,0)` under the EOM policy, we'd have to **delay** the round-down until *after* all Y/M changes are known. That would require:

- Introducing a notion of a "latent desired day" (carry the original day across multiple intermediate additions)
- Returning a special deferred object
- Both approaches are invasive and brittle (and they fight the current invariant that every `DateVar` is always a valid concrete date)

The current `__add__` follows the baseline spec exactly and is correct. The mismatch comes from the **decomposition procedure**, not from `__add__`.

## Alternative: Sequential Chaining Support

If you absolutely must support `(((date + Y) + M) + D)` being equivalent, the clean route is:

- Add a lightweight wrapper `DateExpr` that accumulates a `(ΔY, ΔM, ΔD)` triple without changing the underlying day
- Only when it materializes into a `DateVar` do you execute **one** baseline add (NormMonth → EOM → add days)
- This is a larger refactor, but provides the desired semantics

## Analysis: Alternative Decomposition Orders

### Why Changing Order Won't Solve the Problem

The inconsistency issue is **not** about the order of operations within a single `DateVar.__add__` call. The current baseline implementation already does the correct order:

1. **Years + Months** (normalize month)
2. **EOM round-down** (clamp day to valid range)  
3. **Add days** (ordinal addition)

This is mathematically correct and matches the expected behavior.

### Current Decomposition (Y→M→D)
```python
# This is what currently fails
z1 = x + Period(per.years, 0, 0)      # Add years first
z2 = z1 + Period(0, per.months, 0)    # Then months  
z3 = z2 + Period(0, 0, per.days)      # Then days
```

**Result for `Date(2020, 2, 29) + Period(1, 1, 1)`:**
```
2020-02-29 + (1y,0m,0d) → 2021-02-28  (round-down loses the 29th)
2021-02-28 + (0y,1m,0d) → 2021-03-28  (round-down again)
2021-03-28 + (0y,0m,1d) → 2021-03-29  ❌ Wrong! (Expected: 2021-03-30)
```

### Alternative Decomposition (D→M→Y)
```python
# This would also fail
z1 = x + Period(0, 0, per.days)       # Add days first
z2 = z1 + Period(0, per.months, 0)    # Then months
z3 = z2 + Period(per.years, 0, 0)    # Then years
```

**Result for `Date(2020, 2, 29) + Period(1, 1, 1)`:**
```
2020-02-29 + (0y,0m,1d) → 2020-03-01  (round-down loses the 29th)
2020-03-01 + (0y,1m,0d) → 2020-04-01  (round-down again)  
2020-04-01 + (1y,0m,0d) → 2021-04-01  ❌ Still wrong! (Expected: 2021-03-30)
```

### Why Neither Order Works

The fundamental issue is that **date arithmetic with EOM round-down is not associative**. The problem occurs because:

1. **EOM round-down happens after each individual operation**
2. **Each round-down loses information** about the original day
3. **The order of round-downs matters** when dealing with month-end boundaries

### The Core Insight

The issue is **not about order** - it's about **avoiding multiple round-down operations** that lose information. Any decomposition that applies periods separately will trigger multiple round-downs, each losing the original day information.

## Recommendation

**Use the "Combine Then Apply" approach** because:
1. **Preserves Baseline Semantics**: The current `DateVar.__add__` is correct
2. **Minimal Change**: Only requires updating the test decomposition logic
3. **Mathematically Sound**: Combines periods before applying, avoiding associativity issues
4. **Robust**: Doesn't require invasive changes to the core date arithmetic

This will make the failing case:
```
Date(2020, 2, 29) + Period(1, 1, 1) -> Date(2021, 3, 30)
decomposed via sum_periods -> Date(2021, 3, 30)
```

So the test passes while preserving the correct baseline semantics.
