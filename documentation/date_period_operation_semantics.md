## Date–Period Operation Semantics

### Context
Date arithmetic with an end-of-month (EOM) round‑down policy is neither associative nor commutative across year, month, and day components. The order in which year (Y), month (M), and day (D) deltas are applied can change the outcome, especially near month ends and leap‑year boundaries.

### Baseline semantics used in this project
The baseline `date + Period(Y,M,D)` semantics are:
1) Combine Y and M (normalize months into 1..12 with year carry)
2) Apply EOM clamp: day := min(original_day, days_in_month(new_year,new_month))
3) Add D days in ordinal space (exact day arithmetic)

This “combine Y+M, clamp once, then add D” is the canonical one‑shot behavior used by the baseline and matches libraries like `relativedelta` when used all‑at‑once.

---

### Alternative calculation strategies you may encounter
Below are commonly used strategies and how they compare.

1) Add Y first, then M, then D (Y→M→D)
- Behavior: clamps may happen after adding Y, then again after adding M, and finally days are added.
- Pitfall: multiple EOM clamps can lose the original desired day, causing drift.

2) Add M first, then Y, then D (M→Y→D)
- Behavior: similar to (1) but months are applied before years.
- Relation to baseline: sometimes matches the one‑shot result, sometimes not; still susceptible to multiple clamps.

3) Add D first, then M, then Y (D→M→Y)
- Behavior: day arithmetic can move you out of the original month before Y/M adjustments, changing which months you later traverse and how EOM clamps apply.
- Typically diverges from one‑shot.

4) Convert (Y,M) into an equivalent number of days, add days, then handle overflows
- Idea: map months/years to days up front, then do pure ordinal addition.
- Why this is hard for constraints: months have variable length and leap‑day effects; the “days for N months” depends on the path (which months you cross). In an SMT/constraint setting this explodes into piecewise cases over month counts, leap years, and boundaries, harming solver performance and clarity.

5) Convert Y into months and add months first: add (12·Y + M) months, then add D days
- Behavior: combines all month-like movement up front (a single normalization + a single EOM clamp), then performs day arithmetic.
- Relation to baseline: this is equivalent to the one‑shot baseline when implemented as “normalize once, clamp once, then add D days.” It can differ from (2) because (2) may clamp twice (after M, after Y), while (5) clamps only once after the combined months.

---

### Validated examples and why they differ

- Example A: Date(2020, 2, 29) + Period(1, 1, 1)
  - One‑shot baseline (combine Y+M → clamp → +D): 2021‑03‑30
  - (1) Y→M→D: 2021‑03‑29
    - Why: +1y clamps Feb 29 → Feb 28 (non‑leap 2021), then +1m → Mar 28, then +1d → Mar 29; the initial clamp loses the 29th.
  - (2) M→Y→D: 2021‑03‑30
    - Why: +1m from Feb 29 → Mar 29 (no loss), +1y → Mar 29, +1d → Mar 30; here it coincides with one‑shot.
  - (3) D→M→Y: 2021‑04‑01
    - Why: +1d → Mar 1, +1m → Apr 1, +1y → Apr 1; different path entirely.
  - Takeaway: the three decompositions yield different outcomes amongst themselves; only (2) happens to match the one‑shot for this case.

- Example B (5 vs 2 differ): Date(2017, 12, 30) + Period(2, 2, 1)
  - (2) M→Y→D: +2m → 2018‑02‑28 (clamp), +2y → 2020‑02‑28, +1d → 2020‑02‑29
  - (5) (12·Y+M)=26m first, then D: +26m → 2020‑02‑29 (single clamp), +1d → 2020‑03‑01
  - Why different: method (2) clamps twice (after M and after Y), while (5) clamps once after combined months. Crossing a leap boundary changes whether you keep or lose the 29th.

- Example C (1 vs 2 differ): Date(2019, 1, 31) + Period(1, 1, 0)
  - (1) Y→M→D: +1y → 2020‑01‑31, +1m → 2020‑02‑29 (leap‑year Feb), result 2020‑02‑29
  - (2) M→Y→D: +1m → 2019‑02‑28 (clamp), +1y → 2020‑02‑28, result 2020‑02‑28
  - Why different: whether you encounter the leap‑year February before or after clamping determines if you can “keep” the 29th.

---

### Why do these differences happen?
- EOM clamp is lossy: each time you clamp, you may lose the original desired day (e.g., 31 → 30/29/28). Multiple clamps amplify the loss.
- Non‑associativity: (date + Y) + M can differ from date + (Y + M) because the clamp happens after each step in the decomposed routes.
- Leap‑year boundaries: moving across a leap day changes the maximum valid day for February; the timing of that crossing (before/after clamps) determines whether the 29th survives.
- Day‑first routes change the month path: adding days first may move you into a different month set, changing subsequent month/ year effects.

---

### Recommendations
- For correctness and predictability: prefer the one‑shot baseline (combine Y+M, clamp once, then add D days) - the “(12·Y+M) then D” implementation.
- If you must decompose for testing or API ergonomics: combine Y and M before applying, then apply D. Avoid sequences that clamp multiple times.
- Avoid “convert months to days” approaches in symbolic/constraint contexts due to path‑dependent month lengths and leap‑day cases that cause large piecewise encodings.
