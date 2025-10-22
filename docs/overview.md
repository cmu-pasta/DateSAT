# Method Implementation Overview

This document describes the common structure and requirements for implementing symbolic date constraint solving methods in DATE-SMT.

## Data Types

### Concrete Types (from `datesmt.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving (implemented per method)
- **`PeriodVar`**: Not supported - periods are always concrete

## Required Classes

### DateVar Class

Every method must implement a `DateVar` class with:

**Core Properties:**
- `name` - String identifier for the variable
- `to_concrete_date(model)` - Convert Z3 model to concrete `Date` object

**Comparison Operations:**
- `__eq__(other)` - Equality comparison
- `__ne__(other)` - Inequality comparison  
- `__lt__(other)` - Less than comparison
- `__le__(other)` - Less than or equal comparison
- `__gt__(other)` - Greater than comparison
- `__ge__(other)` - Greater than or equal comparison

**Arithmetic Operations:**
- `__add__(other)` - DateVar + Period addition
- `__sub__(other)` - DateVar - Period subtraction

**Supported Types:**
- `other` can be `Date` (concrete) or `DateVar` (symbolic)
- All operations must raise `TypeError` for unsupported types

**Note**: Periods are always concrete `Period` objects, never symbolic `PeriodVar`. `Period + DateVar` and `Period - DateVar` are not supported (semantically incorrect).

### Solver Class

Every method must implement a solver class with:

**Core Methods:**
- `__init__(timeout_ms=60000)` - Initialize with optional timeout
- `add_date_var(name)` - Create and register a symbolic date variable
- `add_constraint(constraint)` - Add a Z3 constraint to the solver
- `check()` - Check if constraints are satisfiable
- `model()` - Get the Z3 model if satisfiable
- `solve()` - Solve and return results dictionary

**Additional Methods:**
- `get_concrete_dates(model)` - Extract concrete dates from Z3 model
- `to_smt2()` - Return current problem in SMT-LIB v2 format
- `get_assertions()` - Return list of current Z3 assertions

**Result Format:**
```python
{
    'status': 'sat' | 'unsat',
    'dates': {name: Date, ...}  # Only if status is 'sat'
}
```

## Supported Operations

### DateVar Operations

**Fully Supported:**
- DateVar + Period addition
- DateVar - Period subtraction
- DateVar comparisons (==, !=, <, <=, >, >=) with Date or DateVar
- Conversion to concrete Date objects

**Not Supported:**
- Direct DateVar + DateVar arithmetic
- Direct DateVar - DateVar arithmetic
- DateVar multiplication or division

### Period Operations (Concrete Only)

**Fully Supported:**
- Period + Period addition
- Period - Period subtraction
- Period * integer multiplication
- integer * Period multiplication

**Not Supported:**
- PeriodVar (symbolic periods) - not supported
- Period comparisons (==, !=, <, <=, >, >=)
- Period division
- Period multiplication with non-integers

## Implementation Requirements

### Date Validation

All methods must enforce the valid date range:
- **Minimum**: 1900-03-01
- **Maximum**: 2100-02-28

**Range Validation Details**:
- **1900-03-01 to 1900-12-31**: Special handling for first year
- **1901-01-01 to 2099-12-31**: Standard full-year validation
- **2100-01-01 to 2100-02-28**: Special handling for last year (2100 not a leap year)

### Error Handling

- **TypeError**: For unsupported operand types
- **ValueError**: For invalid date ranges or components
  - Invalid date format: "year, month, and day must be integers"
  - Invalid date: "Invalid date: YYYY-MM-DD"
  - Date outside allowed range: "Date outside allowed range: YYYY-MM-DD (allowed [1900-03-01..2100-02-28])"
- **Z3 exceptions**: For solver-specific errors

### Input Validation

- **Type Checking**: All date components must be integers (booleans explicitly rejected)
- **Range Validation**: Comprehensive validation for supported date range
- **Calendar Correctness**: Uses Python's `date()` constructor for validation

### Z3 Integration

- Use Z3's `Int` sort for integer implementations
- Use Z3's `BitVec` sort for bitvector implementations
- All constraints must be Z3 `BoolRef` objects
- Model evaluation must handle `model_completion=True`

## Glossary

### Technical Terms

- **EOM Clamp**: When adding months to a date, if the original day doesn't exist in the target month (e.g., Jan 31 + 1 month = Feb 31), clamp the day to the last valid day of that month (Feb 28/29)

- **Ordinal Day Arithmetic**: Convert dates to days since a fixed epoch (2000-03-01), perform exact integer arithmetic, then convert back to year/month/day

- **Epoch Arithmetic**: Simple integer addition/subtraction on days since a fixed epoch date

- **Alpha Representation**: Months since epoch month (March 2000 = 0) in alpha/beta methods

- **Beta Representation**: Extra days within a month (0-based, so day = 1 + beta) in alpha/beta methods

- **Lazy Y/M/D**: Y/M/D components are created only when needed for month/year arithmetic (hybrid method)

- **Table-based Lookup**: Use pre-computed arrays instead of calculating days-in-month on-the-fly for performance

- **Decode Epoch**: Convert days since epoch back to year/month/day components

- **Encode to Epoch**: Convert year/month/day back to days since epoch

## Method-Specific Documentation

- [Baseline](baseline.md) - Direct year/month/day representation
- [Epoch Days](epoch_days.md) - Days since epoch representation
- [Hybrid](hybrid.md) - Dual epoch + Y/M/D representation
- [Alpha Beta](alpha_beta.md) - Optimized months/days representation
- [Alpha Beta Table](alpha_beta_table.md) - Table-optimized representation

## Implementation Types

- [Integer](implementations.md) - Z3 integer theory
- [Bitvector](implementations.md) - Z3 bitvector theory
