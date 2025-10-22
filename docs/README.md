# DATE-SMT Documentation

This directory contains detailed technical documentation for the DATE-SMT library.

## Documentation Files

### Method Documentation
- **[Baseline](baseline.md)** - Direct year-month-day representation
- **[Epoch Days](epoch_days.md)** - Days since epoch representation  
- **[Hybrid](hybrid.md)** - Dual epoch + Y/M/D representation
- **[Alpha Beta](alpha_beta.md)** - Optimized months/days representation
- **[Alpha Beta Table](alpha_beta_table.md)** - Table-optimized representation

### Decoding Difference Documentation
- **[Integer vs Bitvector](int_vs_bv.md)** - Decoding type differences

### General Documentation
- **[Overview](overview.md)** - Common structure and requirements for method implementations

## Quick Reference

### Available Methods
- `baseline` - Direct year-month-day representation
- `epoch_days` - Days since epoch representation
- `hybrid` - Combination approach
- `alpha_beta` - Optimized constraint generation
- `alpha_beta_table` - Table-based optimization

### Available Decoding Implementations
- `int` - Z3 integer theory
- `bitvector` - Z3 bitvector theory
