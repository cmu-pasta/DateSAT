# DATE-SMT Test Suite

This directory contains comprehensive tests for the DATE-SMT library, organized by test type and functional categories.

## Test Organization

### Unit Tests (tests/unit_tests/)
Traditional unit tests that test individual functions and methods with specific inputs:
- core_data_structures/ - Tests for Date and Period classes
- date_validation/ - Tests for leap year and days-in-month validation
- algorithm_specific/ - Tests for baseline vs advanced algorithm implementations

### Property-Based Tests (tests/property_tests/)
Tests that verify mathematical properties and invariants using generated test data with Hypothesis:
- test_date_properties.py - Property tests for Date class
- test_period_properties.py - Property tests for Period class
- test_epoch_properties.py - Property tests for epoch conversion functions

### Integration Tests (tests/integration_tests/)
End-to-end tests using real-world constraint datasets:
- test_constraint_datasets.py - Tests using LLM-generated constraint datasets
- data/ - Test datasets (constraints1.json, constraints2.json)

## Running Tests

### Run All Tests
```bash
pytest tests/
# or
python run_tests.py --category all
```

### Run by Test Type
```bash
# Unit tests only
python run_tests.py --category unit

# Property-based tests only
python run_tests.py --category property

# Integration tests only
python run_tests.py --category integration
```

### Run by Functional Category
```bash
# Core data structures only
python run_tests.py --category core

# Date validation only
python run_tests.py --category validation

# Algorithm-specific tests only
python run_tests.py --category algorithm
```

### Advanced Options
```bash
# Run with verbose output
python run_tests.py --category all --verbose

# Run with coverage reporting
python run_tests.py --category all --coverage

# Run tests in parallel
python run_tests.py --category all --parallel
```

## Java-backed LocalDate ground-truth tests

We use Java's `java.time.LocalDate.plus(Period)` as an external ground truth for date+period semantics.

- Helper program: `tests/unit_tests/general/java/LocalDateGroundTruth.java`
  - CLI: `java -cp tests/unit_tests/general/java LocalDateGroundTruth <year> <month> <day> <perYears> <perMonths> <perDays>`
  - Output: `YYYY-MM-DD`

- Test files:
  - `tests/unit_tests/general/test_date_period_operation_java.py`
    - Compares Java output to canonical ground truth test cases
    - Verifies each solver (baseline/advanced/hybrid) matches that ground truth
  - `tests/unit_tests/general/test_date_period_decomposition_java.py`
    - Tests decomposed additions in different orders (Y→M→D, M→Y→D, D→M→Y, D→Y→M)
    - Uses Java results for each decomposed order as ground truth
    - Verifies each solver matches Java for each order

- Requirements: Java toolchain on PATH
```bash
java -version
javac -version
# If missing (macOS/Homebrew):
brew install openjdk
# Then ensure PATH includes the Java bin directory
export JAVA_HOME=$(/usr/libexec/java_home)  # or /opt/homebrew/opt/openjdk
export PATH="$JAVA_HOME/bin:$PATH"
```

- Running only the Java-backed operation tests:
```bash
pytest -q tests/unit_tests/general/test_date_period_operation_java.py
```

- Running only Java-vs-ground-truth assertions in that file:
```bash
pytest -q tests/unit_tests/general/test_date_period_operation_java.py -k java_output_equals_ground_truth
```

- Selecting solvers via markers (works in both Java-backed test files):
```bash
# Baseline only
pytest -q tests/unit_tests/general/test_date_period_operation_java.py -m baseline

# Advanced only
pytest -q tests/unit_tests/general/test_date_period_operation_java.py -m advanced

# Hybrid only
pytest -q tests/unit_tests/general/test_date_period_operation_java.py -m hybrid
```

- Running the decomposed-order tests:
```bash
pytest -q tests/unit_tests/general/test_date_period_decomposition_java.py
# or select a solver subset
pytest -q tests/unit_tests/general/test_date_period_decomposition_java.py -m baseline
```
