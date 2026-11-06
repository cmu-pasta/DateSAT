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

# Test specific encoding theory
pytest tests/ -m int
pytest tests/ -m bitvector

# Test specific encoding theory with specific method
pytest tests/unit_tests/int -m simple
```

### Validation suites (not run by default)

The translation validation (`tests/translation_validation`, Z3 checks of the generated
terms against the Verus spec) and the spec adequacy tests (`tests/spec_adequacy`, the Verus
reference semantics against the compiled Verus oracle, `datetime` and `java.time`) are
slow and need extra tooling, so the default `pytest` run leaves them out. Run them on request:

```bash
pytest -m translation_validation
pytest -m spec_adequacy          # needs proofs/build/datesat-oracle and java
```
