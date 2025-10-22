# Baseline Method

The baseline method uses direct year-month-day representation for dates and performs component-wise arithmetic with proper normalization.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

**Variables**: Three separate Z3 integer variables
- `year` - Year component (1900-2100)
- `month` - Month component (1-12) 
- `day` - Day component (1-31, varies by month/year)

**Constraints**: Direct validation of year/month/day ranges with leap year handling

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

1. **Combine Y and M**: Convert period years to months and normalize
   - `total_months = current_month + (period_years * 12 + period_months)`
   - Normalize months to 1-12 range with year carry

2. **EOM Clamp**: Handle end-of-month rollover
   - **EOM Clamp**: When adding months to a date, if the original day doesn't exist in the target month (e.g., Jan 31 + 1 month = Feb 31), clamp the day to the last valid day of that month (Feb 28/29)
   - `day = min(original_day, days_in_month(new_year, new_month))`

3. **Add Days**: Convert dates to days since EPOCH (2000-03-01), perform exact integer arithmetic, then convert back to year/month/day

### DateVar Comparisons

- **Direct component comparison**: Compare year, then month, then day

### Implementation Classes

- `DateVar` - Symbolic date variable with year/month/day components
- `BaselineSolver` - Constraint solver with comprehensive date validation
- Helper functions: `is_leap()`, `days_in_month()`, `normalize_month()`, `eom_clamp()`, `days_before_year()`, `days_before_month()`, `to_ordinal()`, `from_ordinal()`, `ymd_from_days_since_epoch()`, `days_since_epoch_from_ymd()`, `add_days_ordinal()`
