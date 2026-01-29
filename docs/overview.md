# Method Implementation Overview

This document describes the common structure and requirements for implementing a new encoding for DateSAT solver.

## Data Types

### Concrete Types (from `datesat.core`)
- **`Date`**: Concrete date with year, month, day components
- **`Period`**: Concrete period with years, months, days components

### Symbolic Types
- **`DateVar`**: Symbolic date variable for constraint solving (implemented per method)

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
- `__init__(timeout_ms=600000)` - Initialize with optional timeout
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

### Error Handling

- **TypeError**: For unsupported operand types
- **ValueError**: For invalid date ranges or components
  - Invalid date format: "year, month, and day must be integers"
  - Invalid date: "Invalid date: YYYY-MM-DD"
  - Date outside allowed range: "Date outside allowed range: YYYY-MM-DD (allowed [1900-03-01..2100-02-28])" (Optional)
  - Invalid Period format: "years, months, and days must be integers"
  - Period years out of range: "Period years out of range: YYYY (max ±200)" (Optional)
  - Period months out of range: "Period months out of range: MMMM (max ±2400)" (Optional)
  - Period days out of range: "Period days out of range: DDDD (max ±73048)" (Optional)
- **Z3 exceptions**: For solver-specific errors

### Input Validation

- **Type Checking**: All date components must be integers (booleans explicitly rejected)
- **Calendar Correctness**: Uses Python's `date()` constructor for validation
- **Range Validation**: Comprehensive validation for supported date range (Optional)
