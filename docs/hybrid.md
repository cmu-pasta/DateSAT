# Hybrid Method

The hybrid method uses dual representation: epoch-primary with lazy Y/M/D derivation.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

**Primary**: Epoch-based representation
- `epoch_var` - Days since epoch (2000-03-01)
- Range: -36525 to 36523 (covers 1900-03-01 to 2100-02-28)

**Secondary**: Lazy Y/M/D components (created on demand)
- `year_var` - Year component (derived from epoch)
- `month_var` - Month component (derived from epoch)  
- `day_var` - Day component (derived from epoch)

**Constraints**: Forward link ensures `epoch_var == days_since_epoch_from_ymd(year, month, day)`

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

1. **Add Days Only**: If period has only days, add directly to epoch_var
   - `result.epoch_var = self.epoch_var + period_days`

2. **Add Months/Years**: Use existing Y/M/D or decode epoch
   - **Lazy Y/M/D**: Y/M/D components are created only when needed for month/year arithmetic
   - If Y/M/D exists and consistent: use directly
   - Otherwise: decode epoch to Y/M/D using `from_days_since_epoch()` (reused from epoch_days)
   - Apply baseline semantics (reuses `normalize_month()`, `eom_clamp()`, `add_days_ordinal()` from baseline)
   - Set result Y/M/D (epoch derived on demand)

### DateVar Comparisons

- **Epoch-based**: Use primary epoch representation

### Implementation Classes

- `DateVar` - Symbolic date variable with dual representation
- `HybridSolver` - Constraint solver with epoch range validation
- Helper functions: `from_days_since_epoch()` (reused from epoch_days), `to_days_since_epoch()` (reused from epoch_days), `is_leap()` (reused from baseline), `days_in_month()` (reused from baseline), `normalize_month()` (reused from baseline), `days_before_year()` (reused from baseline), `days_before_month()` (reused from baseline), `to_ordinal()` (reused from baseline), `from_ordinal()` (reused from baseline), `ymd_from_days_since_epoch()` (reused from baseline), `days_since_epoch_from_ymd()` (reused from baseline), `eom_clamp()` (reused from baseline), `add_days_ordinal()` (reused from baseline)
