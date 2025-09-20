# DATE-SMT Unit Tests

This directory contains comprehensive unit tests for the DATE-SMT library, organized by functional categories.

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test Categories
```bash
# Core data structures only
pytest tests/core_data_structures/

# Date validation only
pytest tests/date_validation/

# All tests with verbose output
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=datesmt --cov-report=html
```
