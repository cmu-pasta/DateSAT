# DATE-SMT Test Suite

This directory contains unit, property-based, and integration tests for the DATE-SMT library.

## Layout

- `unit_tests/`
  - `core_data_structures/`: Tests for core `Date` and `Period`
  - `int/`: Integer backend tests
  - `bitvector/`: Bitvector backend tests 
- `property_tests/`
  - Hypothesis-based property tests for dates, periods, epoch conversions, and cross-language equivalence
- `integration_tests/`
  - End-to-end runner and validation utilities
  - Dataset in `integration_tests/data/`

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

# Integration tests (runner + validation)
pytest tests/integration_tests
```

### Integration test specific
```bash
# Execute a dataset with execution (run toward datesmt and get the result) + analysis (analyze results' correctness)
python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints1.json --output-dir tests/integration_tests/results/constraints1

# Skip analysis
python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints1.json --output-dir tests/integration_tests/results/constraints1 --no-analysis
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
