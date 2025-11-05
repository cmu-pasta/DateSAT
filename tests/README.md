# DATE-SMT Test Suite

This directory contains unit and property-based tests for the DATE-SMT library.

## Layout

- `unit_tests/`
  - `core_data_structures/`: Tests for core `Date` and `Period`
  - `int/`: Integer backend tests
  - `bitvector/`: Bitvector backend tests 
- `property_tests/`
  - Hypothesis-based property tests for dates, periods, epoch conversions, and cross-language equivalence

## Running tests

### All tests
```bash
pytest tests/
```

### By group
```bash
# Unit tests
pytest tests/unit_tests

# Property-based tests
pytest tests/property_tests
```

### Testing specific methods
Use pytest markers to test specific symbolic backends:

```bash
# Test specific backends
pytest tests/ -m baseline
pytest tests/ -m epoch_days
pytest tests/ -m hybrid
pytest tests/ -m alpha_beta
pytest tests/ -m alpha_beta_table

# Test specific implementations
pytest tests/ -m int
pytest tests/ -m bitvector

# Test specific backend with specific method
pytest tests/unit_tests/int -m baseline
```
