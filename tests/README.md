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
