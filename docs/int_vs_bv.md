# Integer vs Bitvector Implementations

This document explains the differences between integer and bitvector implementations across all symbolic methods in DATE-SMT.

## Overview

Each symbolic method is available in two Z3 implementation types:

- **Integer (int)**: Uses Z3's integer theory (`IntSort`)
- **Bitvector (bv)**: Uses Z3's bitvector theory (`BitVecSort`)

DATE-SMT's bitvector implementations share a legacy width constant,
`LEGACY_BITS = 21` (`datesmt/symbolic_bitvector/bitwidths.py`). Each solver uses
this 21-bit width for variables and literals.

The differences are **consistent across all methods** (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table).

## Core Differences

### Z3 Types Used

| Component | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Variables | `Int(name)` | `BitVec(name, 21)` |
| Constants | `IntVal(value)` | `BitVecVal(value, 21)` |
| Date Components | `Int("year")`, `Int("month")`, `Int("day")` | `BitVec("year", 21)`, `BitVec("month", 21)`, `BitVec("day", 21)` |
| Epoch Values | `IntVal(730179)` | `BitVecVal(730179, 21)` |
| Arithmetic Constants | `IntVal(4)`, `IntVal(100)`, `IntVal(400)` | `BitVecVal(4, 21)`, `BitVecVal(100, 21)`, `BitVecVal(400, 21)` |

### Arithmetic Operations

| Operation | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Division | `a / b` (natural division) | `a / b` (truncating division) |
| Modulo | `a % b` (natural modulo) | `a % b` (bitvector modulo) |
| Comparisons | `a == b`, `a < b`, etc. | `a == b`, `a < b`, etc. |
| Range Checks | Direct integer comparisons | `UGE(a, BitVecVal(2**20, 21))` for signed checks |

### Model Evaluation

| Operation | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Extract Values | `.as_long()` | `.as_signed_long()` |
| Handle Negative | Natural signed integers | Explicit signed conversion |

### Month Normalization

| Aspect | Integer Implementation | Bitvector Implementation |
|--------|----------------------|-------------------------|
| Logic | Simple integer division/modulo | Complex signed arithmetic with floor division |
| Overflow | Assumes infinite precision | Handles 21-bit wraparound explicitly |
| Negative Months | Natural handling | Explicit signed conversion and clamping |
| Floor Division | Natural `//` operator | Custom `_floor_div_12()` function |
| Signed Conversion | Not needed | `If(is_negative, x - BitVecVal(2**21, 21), x)` |
| Remainder Check | Simple `r != 0` | `And(UGE(signed_x, BitVecVal(2**20, 21)), r != BitVecVal(0, 21))` |

## Method-Specific Examples

### Baseline Method
- **Integer**: `normalize_month(y, m)` uses simple `(m-1) // 12` and `(m-1) % 12`
- **Bitvector**: Complex signed arithmetic with `UGE` checks and floor division
  - Checks for negative values: `UGE(m, BitVecVal(2**20, 21))`
  - Converts to signed: `If(is_negative, m - BitVecVal(2**21, 21), m)`
  - Implements floor division manually with remainder checks

### Epoch Days Method
- **Integer**: `days_var = Int("days")` with `IntVal(36525)` for range constraints
- **Bitvector**: `days_var = BitVec("days", 21)` with `BitVecVal(36525, 21)`

### Alpha/Beta Methods
- **Integer**: `months_var = Int("months")`, `beta_var = Int("beta")`
- **Bitvector**: `months_var = BitVec("months", 21)`, `beta_var = BitVec("beta", 21)`

### Hybrid Method
- **Integer**: `epoch_var = Int("epoch")` with lazy `Int("year")`, `Int("month")`, `Int("day")`
- **Bitvector**: `epoch_var = BitVec("epoch", 21)` with lazy `BitVec("year", 21)`, etc.
