# Integer vs Bitvector Implementations

This document explains the differences between integer and bitvector implementations across all symbolic methods in DATE-SMT.

## Overview

Each symbolic method is available in two Z3 implementation types:

- **Integer (int)**: Uses Z3's integer theory (`IntSort`)
- **Bitvector (bv)**: Uses Z3's bitvector theory (`BitVecSort`)

The differences are **consistent across all methods** (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table).

## Core Differences

### Z3 Types Used

| Component | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Variables | `Int(name)` | `BitVec(name, 32)` |
| Constants | `IntVal(value)` | `BitVecVal(value, 32)` |
| Date Components | `Int("year")`, `Int("month")`, `Int("day")` | `BitVec("year", 32)`, `BitVec("month", 32)`, `BitVec("day", 32)` |
| Epoch Values | `IntVal(730179)` | `BitVecVal(730179, 32)` |
| Arithmetic Constants | `IntVal(4)`, `IntVal(100)`, `IntVal(400)` | `BitVecVal(4, 32)`, `BitVecVal(100, 32)`, `BitVecVal(400, 32)` |

### Arithmetic Operations

| Operation | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Division | `a / b` (natural division) | `a / b` (truncating division) |
| Modulo | `a % b` (natural modulo) | `a % b` (bitvector modulo) |
| Comparisons | `a == b`, `a < b`, etc. | `a == b`, `a < b`, etc. |
| Range Checks | Direct integer comparisons | `UGE(a, BitVecVal(2^31, 32))` for signed checks |

### Model Evaluation

| Operation | Integer Implementation | Bitvector Implementation |
|-----------|----------------------|-------------------------|
| Extract Values | `.as_long()` | `.as_signed_long()` |
| Handle Negative | Natural signed integers | Explicit signed conversion |

### Month Normalization

| Aspect | Integer Implementation | Bitvector Implementation |
|--------|----------------------|-------------------------|
| Logic | Simple integer division/modulo | Complex signed arithmetic with floor division |
| Overflow | Assumes infinite precision | Handles 32-bit overflow explicitly |
| Negative Months | Natural handling | Explicit signed conversion and clamping |

## Method-Specific Examples

### Baseline Method
- **Integer**: `normalize_month(y, m)` uses simple `(m-1) // 12` and `(m-1) % 12`
- **Bitvector**: Complex signed arithmetic with `UGE` checks and floor division

### Epoch Days Method
- **Integer**: `days_var = Int("days")` with `IntVal(36525)` for range constraints
- **Bitvector**: `days_var = BitVec("days", 32)` with `BitVecVal(36525, 32)`

### Alpha/Beta Methods
- **Integer**: `months_var = Int("months")`, `beta_var = Int("beta")`
- **Bitvector**: `months_var = BitVec("months", 32)`, `beta_var = BitVec("beta", 32)`

### Hybrid Method
- **Integer**: `epoch_var = Int("epoch")` with lazy `Int("year")`, `Int("month")`, `Int("day")`
- **Bitvector**: `epoch_var = BitVec("epoch", 32)` with lazy `BitVec("year", 32)`, etc.
