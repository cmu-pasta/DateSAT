# Epoch Days Method

The epoch days method uses a single integer representation (days since epoch) for dates and performs arithmetic using ordinal day calculations.

## Data Types

### Concrete Types (from `datesat.core`)
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

2. **Add Months/Years**: Convert to Y/M/D, perform month/year addition, convert back to epoch
   - Convert current date to year/month/day using `ymd_from_days_since_epoch()`
   - Add period months/years using component-wise arithmetic (reuses `normalize_month()` from simple)
   - Apply EOM clamp (reuses `eom_clamp()` from simple)
   - If period has days component, add using `add_days_ordinal()` (converts Y/M/D back to epoch and adds days)
   - Otherwise, convert Y/M/D back to epoch using `days_since_epoch_from_ymd()`

### DateVar Comparisons

- **Direct epoch comparison**: Compare days_var directly

### Implementation Classes

- `DateVar` - Symbolic date variable with days since epoch
- `EpochDaysSolver` - Constraint solver with epoch-based validation
- Helper functions: `ymd_from_days_since_epoch()`, `days_since_epoch_from_ymd()`, `add_days_ordinal()`, `normalize_month()` (reused from simple), `eom_clamp()` (reused from simple)
