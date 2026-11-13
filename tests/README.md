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
pytest tests/ -m alpha_beta

# Test a specific method within a directory
pytest tests/unit_tests/int -m simple
```

### Validation suites (not run by default)

The differential tests (`tests/differential`, every encoding on random constraints,
with each model checked against the reference semantics) and the semantics-vs-libraries
tests (`tests/semantics_vs_libraries`, the Verus reference semantics against Python's
`datetime`/`dateutil` and `java.time`) are slower or need extra tooling, so the default
`pytest` run leaves them out. Run them on request:

```bash
pytest -m differential
pytest -m semantics_vs_libraries   # needs proofs/build/datesat-oracle and java
```
