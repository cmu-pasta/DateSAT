# Alpha Beta Table Method

The alpha beta table method extends the alpha beta approach with pre-computed lookup tables for maximum performance, particularly for repeated operations.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

**Variables**: Two Z3 integer variables
- `months_var` (alpha) - Months since epoch month (March 2000 = 0)
- `beta_var` (beta) - Extra days within that month (0-based, so day = 1 + beta)

**Tables**: Pre-computed lookup tables for days-in-month calculations
- `_DIM48_LIST` - 48-element array for days in month patterns
- `_T1900_FEB`, `_T2100_FEB` - Special handling for century February

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

1. Add period months to alpha
   - `period_alpha = period_years * 12 + period_months`
   - `new_alpha = current_alpha + period_alpha`

2. **Table-based EOM Clamp**: Use pre-computed arrays instead of calculating days-in-month on-the-fly
   - `idx = mod48(new_alpha)` - Get table index (modulo 48 for 4-year leap cycle)
   - `abs_month = alpha_to_abs_month(new_alpha)` - Get absolute month number
   - `dim = Select(_DIM48_LIST, idx)` - Lookup days in month from table
   - Handle century February special case (2100 is not a leap year)

3. **Add Days**: Use pre-computed 48-month tables to add days without converting to ordinal days
   - Calculate total days using `base48 + century_correction + days_delta`
   - Use 4-year cycle arithmetic with table lookups for month boundaries
   - Handle end-of-month overflow with month carry

### DateVar Comparisons

- **Alpha comparison**: Compare months since epoch first
- **Beta comparison**: If alpha equal, compare days within month
- **Efficient**: O(1) complexity for comparisons

### Implementation Classes

- `DateVar` - Symbolic date variable with alpha/beta components
- `AlphaBetaTableSolver` - Constraint solver with table-based validation
- Helper functions: `months_since_epoch_from_ym()`, `alpha_to_abs_month()`, `mod48()`, `_override_dim_for_century_feb()`, `_century_correction()`, `eom_clamp()`, `build_dim_dbm_48_from_epoch()`, `const_array()`, `days_in_month()` (reused from baseline), `add_days_ordinal()` (reused from baseline)
