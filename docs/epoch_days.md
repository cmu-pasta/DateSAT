# Epoch Days Method

The epoch days method uses a single integer representation (days since epoch) for dates and performs arithmetic using ordinal day calculations.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

**Variables**: Single Z3 integer variable
- `days_var` - Days since epoch (2000-03-01)
- Range: -36525 to 36523 (covers 1900-03-01 to 2100-02-28)

**Constraints**: Range validation for days within supported date range

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

1. **Add Days Only**: If period has only days, add directly to days_var (fast path)
   - `result.days_var = self.days_var + period_days`
   - Skips all month/year normalization and ordinal conversion

2. **Add Months/Years**: Convert to ordinal days, add, convert back (similar to naive)
   - Convert current date to year/month/day using `from_days_since_epoch()`
   - Add period months/years using component-wise arithmetic (reuses `normalize_month()` from naive)
   - Add days using `add_days_ordinal()` which includes:
     - Fast path: If result stays within same month, use simple addition (avoids ordinal conversion)
     - Otherwise: Convert to ordinal days, add, convert back to year/month/day
   - Convert year/month/day back to days since epoch using `to_days_since_epoch()`

### DateVar Comparisons

- **Direct epoch comparison**: Compare days_var directly

### Implementation Classes

- `DateVar` - Symbolic date variable with days since epoch
- `EpochDaysSolver` - Constraint solver with epoch-based validation
- Helper functions: `from_days_since_epoch()`, `to_days_since_epoch()`, `is_leap()` (reused from naive), `days_in_month()` (reused from naive), `normalize_month()` (reused from naive), `days_before_year()` (reused from naive), `days_before_month()` (reused from naive), `to_ordinal()` (reused from naive), `from_ordinal()` (reused from naive), `ymd_from_days_since_epoch()` (reused from naive), `days_since_epoch_from_ymd()` (reused from naive), `eom_clamp()` (reused from naive), `add_days_ordinal()` (reused from naive)
