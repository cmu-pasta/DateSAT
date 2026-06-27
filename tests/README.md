# DateSAT Test Suite

This directory contains unit and property-based tests for the DateSAT library.

## Running tests

### All tests
```bash
pytest tests/
```

### Testing specific methods
Use pytest markers to test specific symbolic backends:

```bash
# Test specific backends
pytest tests/ -m simple
pytest tests/ -m epoch_days
pytest tests/ -m hybrid
pytest tests/ -m alpha_beta
pytest tests/ -m alpha_beta_table

# Test specific encoding theory
pytest tests/ -m int
pytest tests/ -m bitvector

# Test specific encoding theory with specific method
pytest tests/unit_tests/int -m simple
```
