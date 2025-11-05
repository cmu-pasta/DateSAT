# DATE-SMT

[![CI Badge](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml/badge.svg)](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml)
[![Coverage Badge](https://pastalab.org/Date-SMT/badge.svg)](https://pastalab.org/Date-SMT/)

A Python library for symbolic analysis of date computations using Z3.

## Overview

DATE-SMT provides multiple implementations for expressing and solving date constraints using Z3. It converts DATE-SMT expressions into Z3 constraints (expressed through integer or bitvector) for efficient symbolic analysis.

## Supported Ranges

### Date Range

All `Date` objects must fall within the following range:
- **Minimum**: 1900-03-01
- **Maximum**: 2100-02-28

Dates outside this range will raise a `ValueError` during construction. 

### Period Range

All `Period` objects must fall within the following bounds (based on the date range):
- **Years**: ±200 (maximum absolute value)
- **Months**: ±2400 (maximum absolute value, equivalent to ±200 years)
- **Days**: ±73048 (maximum absolute value, equivalent to the full date range span)

Periods exceeding these bounds will raise a `ValueError` during construction.

## Installation

```bash
# 1. Setup conda environment
conda create -y -n datesmt python=3.10
conda activate datesmt

# 2. Install dependencies
pip install -r requirements/core.txt
# Optionally install the dev dependencies and the llm constraints generation pipeline dependencies
pip install -r requirements/dev.txt
pip install -r requirements/llm_pipeline.txt

# 3. Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## Repository Structure

- `datesmt/` - Core library with data types and symbolic backends
  - `core.py` - Date and Period data structures
  - `symbolic_int/` - Integer-based symbolic backends (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table)
  - `symbolic_bitvector/` - Bitvector-based symbolic backends (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table)
- `tests/` - Test suite (see `tests/README.md` for details)
- `docs/` - Technical documentation (methods, implementations)
- `dataset/LLM_gen_constraints/` - LLM-based constraint generation and testing tools
  - `generator/` - Constraint generation scripts (llm_client.py, combine_constraints.py)
  - `constraints/` - Generated constraint JSON files
  - `run_tests.py` - Test runner for executing constraints against all DATE-SMT approaches
  - `validation.py` - Concrete validation for verifying solver solutions
  - `test_validation.py` - Unit tests for validation functionality
- `requirements/` - Python dependencies

## Testing

Run all tests:
```bash
pytest tests/
```

Run tests and build the coverage site locally:
```bash
# from repo root
python tests/build_coverage_site.py
# output will be under documentation/coverage by default
# to match Pages layout locally, write directly into docs/
COVERAGE_SITE_DIR=docs python tests/build_coverage_site.py
open docs/index.html  # macOS
```
The coverage site root serves the detailed coverage report.

For detailed testing information including method-specific tests, see `tests/README.md`.

## Development

### Pre-commit Hooks
This project uses pre-commit hooks to ensure code quality. Install and set up.

### CI/CD Pipeline
- **Trigger**: On each push to `dev` branch
- **Coverage**: Automatically builds coverage site and commits to `docs/` directory
- **GitHub Pages**: Serves coverage reports from `docs/` folder
- **Coverage Collection**: Uses `coverage.py` via `pytest-cov` for branch and line coverage
