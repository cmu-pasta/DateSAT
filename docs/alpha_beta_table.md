# Alpha Beta Table Method

The alpha beta table method extends the alpha beta approach with pre-computed lookup tables for maximum performance, particularly for repeated operations.

## Data Types

### Concrete Types (from `datesat.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

**Variables**: Two Z3 integer variables
- `months_var` (alpha) - Months since epoch month (March 2000 = 0)
- `beta_var` (beta) - Extra days within that month (0-based, so day = 1 + beta)

**Tables**: Pre-computed lookup tables covering a 4-year (48-month) cycle
- `_DIM48_LIST` - 48-element array for days in month (indexed by `alpha % 48`)
- `_DBM48_LIST` - 48-element array for days before month within 4-year cycle

**Constraints**: Range validation for alpha and beta within supported date range

## Supported Operations

- DateVar +- Period
- DateVar comparisons (==, !=, <, <=, >, >=) with Date or DateVar

From core.py
- Period +- Period
- Period * Int
- Int * Period
- Date +- Period

**Note**: `Period + DateVar` and `Period - DateVar` are not supported (semantically invalid)
**Note**: Date or DateVar +- Date or DateVar is not supported
**Note**: PeriodVar (symbolic periods) is not supported
**Note**: Period comparison is not supported: periods are not comparable

## Operations Implementation

### DateVar + Period

**Optimizations:**
- **Days-only fast path**: If period has only days (years=0, months=0), skip month shift
  - **Within-month check**: If `beta + days_delta` stays in `[0, dim)`, use simple addition
  - **Otherwise**: Use 48-month table lookup to normalize across month boundaries
- **Years/months-only fast path**: If period has no days component, skip day addition step
- **Within-month fast path**: When adding days, if result stays within same month, skip table lookup and use simple addition

**Full Path (when months/years are present):**

1. Add period months to alpha
   - `period_alpha = period_years * 12 + period_months`
   - `new_alpha = current_alpha + period_alpha`

2. **Table-based EOM Clamp**: Use pre-computed arrays instead of calculating days-in-month on-the-fly
   - `idx = mod48(new_alpha)` - Get table index (modulo 48 for 4-year leap cycle)
   - `dim = Select(_DIM48_LIST, idx)` - Lookup days in month from table
   - Clamp beta to valid range for the target month

3. **Add Days** (if period has days component):
   - **Within-month check**: If `beta1 + days_delta` stays in `[0, dim1)`, use simple addition
   - **Otherwise**: Use pre-computed 48-month tables to normalize
     - Convert current (alpha, beta) to day-of-4-year-cycle: `base48 = DBM48[idx] + beta`
     - Add days: `total = base48 + days_delta`
     - Decompose into 4-year cycles: `q0 = total / 1461`, `r0 = total % 1461`
     - Find target month within cycle by scanning DBM48 table
     - Handle end-of-month overflow with carry: `If(beta2 >= dim2, advance month, keep month)`

### DateVar Comparisons

- **Alpha comparison**: Compare months since epoch first
- **Beta comparison**: If alpha equal, compare days within month
- **Efficient**: O(1) complexity for comparisons

### Implementation Classes

- `DateVar` - Symbolic date variable with alpha/beta components
- `AlphaBetaTableSolver` - Constraint solver with table-based validation
- Helper functions: `months_since_epoch_from_ym()`, `alpha_to_abs_month()`, `mod48()`, `eom_clamp()`, `build_dim_dbm_48_from_epoch()`, `const_array()`, plus internal helpers `_is_leap_py()`, `_days_in_month_py()`, `_add_months()`
