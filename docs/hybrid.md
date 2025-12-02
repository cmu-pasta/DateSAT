# Hybrid Method

The hybrid method uses a dual-lazy representation: both epoch and Y/M/D exist conceptually, and either side is derived lazily only when needed. Neither side is auto-linked to the other; instead, operations derive the required representation on demand.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving
- Note that PeriodVar is not supported - periods are always concrete

## DateVar Representation

- `epoch_var`: Days since epoch (2000-03-01); valid range [-36525, 36523]
- `year_var`, `month_var`, `day_var`: Created lazily when needed
- Consistency flags track which side currently reflects the date value:
  - epoch-consistent: operations can use `epoch_var` directly
  - ymd-consistent: operations can use `(Y, M, D)` directly
- No automatic forward-link. When an operation requires the other side, it derives an expression on demand:
  - epoch on demand: `days_since_epoch_from_ymd(Y, M, D)`
  - Y/M/D on demand: `ymd_from_days_since_epoch(epoch)`

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
- **Days-only fast path**: If period has only days, add to epoch expression directly (avoids Y/M/D conversion)
- **Within-month fast path**: When adding days via `add_days_ordinal()`, if result stays within same month, avoid ordinal conversion

1. **Add Days Only**: If period has only days, add to the epoch expression in-place (fast path)
   - `result.epoch_var = epoch_expr(self) + period_days`
   - Marks result as epoch-consistent (Y/M/D remains lazy)
   - Skips all month/year normalization and Y/M/D conversion

2. **Add Months/Years**: Use Y/M/D terms; derive them on demand if needed
   - If Y/M/D is consistent, use them directly; else derive via `ymd_from_days_since_epoch(epoch_expr(self))`
   - Apply naive semantics (reuse `normalize_month()`, `eom_clamp()`, `add_days_ordinal()`)
   - `add_days_ordinal()` includes within-month fast path to avoid ordinal conversion when possible
   - Constrain only the result Y/M/D; mark result as Y/M/D-consistent (epoch remains lazy and is derived only if/when needed)

### DateVar Comparisons

Comparisons choose the cheapest available consistent representation:
- If both sides have consistent Y/M/D: compare lexicographically on `(Y, M, D)`
- Else if both sides have consistent epoch: compare on `epoch_var`
- Else: derive epoch expressions on demand for the inconsistent side(s) and compare on epoch

### Implementation Classes

- `DateVar` - Symbolic date variable with dual-lazy representation
  - **Constructor**: `DateVar(ctx, name: str)` - Requires solver context and name
  - **Context Integration**: All operations require solver context for constraint management
  - **Lazy derivation**: Y/M/D and epoch are derived on-demand; no auto forward linking
- `HybridSolver` - Constraint solver with epoch range validation
- Helper functions: `from_days_since_epoch()` (reused from epoch_days), `to_days_since_epoch()` (reused from epoch_days), `is_leap()` (reused from naive), `days_in_month()` (reused from naive), `normalize_month()` (reused from naive), `days_before_year()` (reused from naive), `days_before_month()` (reused from naive), `to_ordinal()` (reused from naive), `from_ordinal()` (reused from naive), `ymd_from_days_since_epoch()` (reused from naive), `days_since_epoch_from_ymd()` (reused from naive), `eom_clamp()` (reused from naive), `add_days_ordinal()` (reused from naive)
