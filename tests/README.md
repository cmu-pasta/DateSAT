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
pytest tests/ -m hybrid_init_ymd
pytest tests/ -m hybrid_init_epoch
pytest tests/ -m hybrid          # bitvector implementation only
pytest tests/ -m alpha_beta

# Test specific encoding theory
pytest tests/ -m int
pytest tests/ -m bitvector

# Test specific encoding theory with specific method
pytest tests/unit_tests/int -m simple
```

### Validation suite (not run by default)

The semantics-vs-libraries tests (`tests/semantics_vs_libraries`, the Verus reference semantics against Python's `datetime`/`dateutil` and `java.time`) need extra tooling, so the default `pytest` run leaves them out. Run them on request:

```bash
pytest -m semantics_vs_libraries   # needs proofs/build/datesat-oracle and java
```
