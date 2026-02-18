# Integer vs Bitvector Theory for DateSAT Encodings

This document explains the differences between integer and bitvector implementations across all symbolic methods in DateSAT.

## Overview

Each symbolic method is available in two Z3 implementation types:

- **Integer (int)**: Uses Z3's integer theory (`IntSort`)
- **Bitvector (bv)**: Uses Z3's bitvector theory (`BitVecSort`)

DateSAT's bitvector implementations share a legacy width constant, `LEGACY_BITS = 21` (`datesat/symbolic_bitvector/bitwidths.py`). 
Each solver uses this 21-bit width for variables and literals.

## Core Differences

Below differences are **consistent across all methods** (naive, epoch_days, hybrid, alpha_beta, alpha_beta_table).

### Important Difference

To avoid bitvector overflows, we currently bound concrete integer and integer variables to be within [0, 8000].

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

## Encoding-Specific Differences

### Alpha-Beta Table Encoding

How bitvector's Alpha-Beta Table encoding handles converting a day from the (alpha, beta) representation to the single integer days-since-epoch representation is different from int.
Specifically, int's constraints check days since the epoch date (March 1, 2000) directly. However, bitvector's constraints currently check days since ordinal (Jan 1, 0001) instead, and then offset the value with a precomputed number of days of the epoch date since ordinal. This is because it is tricky for the bitvector encodings to handle negative values.
