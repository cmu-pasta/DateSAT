# Investigation Summary: Baseline Solver UNSAT Issues

## Problem Overview
The baseline symbolic solver is returning `UNSAT` (unsatisfiable) for many simple date arithmetic operations that should be satisfiable. This affects 22 out of 68 test cases in the component decomposition tests.

## Root Cause Analysis

### Primary Issue: Ordinal Date Conversion Functions
The problem lies in the `add_days_ordinal` function, specifically in the `_days_from_civil` and `_civil_from_days` functions. These functions implement complex Gregorian calendar arithmetic using ordinal day numbers, but they create Z3 expressions that are too complex for the solver to handle efficiently.

### Specific Failing Cases
The failing test cases fall into several categories:

1. **Leap Year Edge Cases**:
   - `Date(2020, 2, 29) + Period(1, 0, 0) = Date(2021, 2, 28)` - Adding 1 year to Feb 29 in leap year
   - `Date(2020, 2, 29) + Period(0, 12, 0) = Date(2021, 2, 28)` - Adding 12 months to Feb 29
   - `Date(2020, 2, 29) + Period(0, 48, 0) = Date(2024, 2, 29)` - Adding 48 months to Feb 29

2. **Month-End to Month-End Transitions**:
   - `Date(2020, 1, 31) + Period(0, 1, 0) = Date(2020, 2, 29)` - Jan 31 + 1 month in leap year
   - `Date(2021, 1, 31) + Period(0, 1, 0) = Date(2021, 2, 28)` - Jan 31 + 1 month in non-leap year
   - `Date(2020, 1, 31) + Period(0, 13, 0) = Date(2021, 2, 28)` - Jan 31 + 13 months

3. **Day Boundary Cases**:
   - `Date(2020, 2, 28) + Period(0, 0, 1) = Date(2020, 2, 29)` - Feb 28 + 1 day in leap year
   - `Date(2020, 2, 29) + Period(0, 0, 1) = Date(2020, 3, 1)` - Feb 29 + 1 day in leap year
   - `Date(2021, 2, 28) + Period(0, 0, 1) = Date(2021, 3, 1)` - Feb 28 + 1 day in non-leap year

4. **Mixed Period Cases**:
   - `Date(2020, 1, 31) + Period(1, 1, 1) = Date(2021, 3, 1)` - Complex mixed period
   - `Date(2020, 2, 29) + Period(1, 1, 1) = Date(2021, 3, 30)` - Complex mixed period with leap year

5. **Zero and Identity Cases**:
   - `test_zero_and_identity_cases` - Even simple zero period addition fails

## Technical Details

### The Problematic Code Path
1. **DateVar.__add__()** calls `add_days_ordinal(y1, m1, d1, other.days)`
2. **add_days_ordinal()** calls `_days_from_civil()` to convert to ordinal
3. **add_days_ordinal()** calls `_civil_from_days()` to convert back from ordinal
4. These functions create extremely complex Z3 expressions that cause UNSAT

### Why It Fails
The `_days_from_civil` and `_civil_from_days` functions implement the Gregorian calendar algorithm using:
- Complex conditional logic with nested `If` expressions
- Multiple modulo operations (`% 4`, `% 100`, `% 400`)
- Integer division operations
- Large constant multiplications (146097, etc.)

When Z3 tries to solve these expressions, it becomes overwhelmed by the complexity and returns UNSAT, even for cases that should be trivially satisfiable.

### Evidence
- Simple cases like `Date(2020, 2, 29) + Period(1, 0, 0)` fail
- The EOMClamp function works correctly (tested separately)
- The normalize_month function works correctly (tested separately)
- The issue is specifically in the ordinal conversion functions

## Impact
- 22 out of 68 test cases fail (32% failure rate)
- Affects all leap year edge cases
- Affects month-end boundary cases
- Affects even simple zero-period cases
- Makes the baseline solver unreliable for date arithmetic

## Recommended Solutions
1. **Simplify the ordinal conversion functions** - Use a more Z3-friendly approach
2. **Implement a different date arithmetic strategy** - Avoid ordinal conversion entirely
3. **Use concrete evaluation for simple cases** - Fall back to Python date arithmetic when possible
4. **Optimize the Z3 expressions** - Reduce complexity of the generated constraints

## Next Steps
The user should decide whether to:
1. Fix the ordinal conversion functions
2. Implement a completely different date arithmetic approach
3. Use a hybrid approach that combines symbolic and concrete evaluation
