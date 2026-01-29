# Alpha Beta Method

The alpha beta method represents dates as (months, days) since an epoch month.

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

**Epoch Constants**:
- `_EPOCH_YEAR = 2000`, `_EPOCH_MONTH = 3`
- `_EPOCH_LINEAR = 12 * 2000 + 3 = 24003` (linearized epoch month)

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
- **Days-only fast path**: If period has only days (years=0, months=0), skip month shift and EOM clamp
  - **Within-month check**: If adding days stays within same month, use simple addition to beta
  - **Otherwise**: Normalize via epoch conversion (converts Y/M/D to epoch days, then back to Y/M/D to handle month overflow)
- **Years/months-only fast path**: If period has no days component, skip day addition step

**Full Path (when months/years are present):**

1. Add period months to alpha
   - `period_alpha = period_years * 12 + period_months`
   - `new_alpha = current_alpha + period_alpha`

2. **EOM Clamp**: When adding months to a date, if the original day doesn't exist in the target month (e.g., Jan 31 + 1 month = Feb 31), clamp the day to the last valid day of that month (Feb 28/29)

3. **Add Days** (if period has days component):
   - **Within-month check**: If `beta + days_delta` stays in `[0, dim)`, use simple addition
   - **Otherwise**: Normalize via epoch conversion
     - Convert Y/M/D to epoch days using `days_since_epoch_from_ymd()`
     - Convert back to Y/M/D using `ymd_from_days_since_epoch()` (handles all overflow cases)
     - Extract alpha (months) and beta (days) from result


### DateVar Comparisons

- **Alpha comparison**: Compare months since epoch first
- **Beta comparison**: If alpha equal, compare days within month

### Implementation Classes

- `DateVar` - Symbolic date variable with alpha/beta components
- `AlphaBetaSolver` - Constraint solver with alpha/beta range validation
- Helper functions: `months_since_epoch_from_ym()`, `ym_from_months_since_epoch()`, `eom_clamp()` (reused from naive), `days_in_month()` (reused from naive), `ymd_from_days_since_epoch()` (reused from epoch_days), `days_since_epoch_from_ymd()` (reused from epoch_days)
