# DATE-SMT

[![CI Badge](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml/badge.svg)](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml)
[![Coverage Badge](https://pastalab.org/Date-SMT/badge.svg)](https://pastalab.org/Date-SMT/)

A Python library for symbolic analysis of date computations using Z3.

## Overview

DATE-SMT provides multiple implementations for expressing and solving date constraints using Z3. It converts DATE-SMT expressions into Z3 constraints (expressed through integer or bitvector arithmetic) for efficient symbolic analysis.

The library offers both a high-level Python API and a command-line interface for solving date constraints with support for:
- Date and period arithmetic
- Integer and boolean variables
- Complex boolean expressions with `&&`, `||`, `!`, and implications (`->`)
- Date component access (`.year`, `.month`, `.day`)
- Multiple solver approaches optimized for different use cases

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

## Quick Start

### Python API

```python
import datesmt

# Solve date constraints
result = datesmt.solve({
    "declarations": ["x: date", "y: date"],
    "constraints": [
        "x >= Date(2024,1,1)",
        "y == x + Period(0,1,0)",
        "x.month == 6"
    ]
})

if result["status"] == "sat":
    print(f"x = {result['dates']['x']}")
    print(f"y = {result['dates']['y']}")
```

### Command-Line Interface

```bash
# From stdin
echo '{"declarations":["x: date"],"constraints":["x >= Date(2024,1,1)"]}' | python bin/datesmt.py

# From file
python bin/datesmt.py --file constraints.json

# With options
python bin/datesmt.py --approach hybrid --implementation bitvector --output json < constraints.json
```

See [USAGE.md](USAGE.md) for comprehensive documentation and examples.

## Constraint Format

Constraints are specified in JSON format with variable declarations and constraint expressions.

### Basic Format

```json
{
  "declarations": ["variable_name: type", ...],
  "constraints": ["constraint_expression", ...]
}
```

**Variable Types:**
- `date` - Date variable
- `int` - Integer variable
- `bool` - Boolean variable

**All constraints in the list are ANDed together.**

### Constraint Language

**Date and Period Constructors:**
- `Date(year, month, day)` - e.g., `Date(2024, 6, 15)`
- `Period(years, months, days)` - e.g., `Period(1, 6, 0)`

**Date Arithmetic:**
- `date + period`, `date - period`
- `period + period`, `period - period`
- `int * period`

*Note: `date - date` is not supported.*

**Date Comparisons:**
- `==`, `!=`, `<`, `<=`, `>`, `>=`

**Date Components:**
- `date.year`, `date.month`, `date.day`

**Boolean Operators:**
- `&&` (AND), `||` (OR), `!` (NOT)
- `->` (implication)

### Examples

**Simple constraints:**
```json
{
  "declarations": ["x: date"],
  "constraints": [
    "x >= Date(2000,2,28)",
    "x <= Date(2000,3,1)"
  ]
}
```

**Boolean operators:**
```json
{
  "declarations": ["x: date"],
  "constraints": [
    "x >= Date(2000,2,28) || x <= Date(2000,2,29)",
    "x != Date(2000,3,1)"
  ]
}
```

**Date components and integer variables:**
```json
{
  "declarations": ["x: date", "n: int"],
  "constraints": [
    "x.year == 2024",
    "n > 5",
    "n < 10"
  ]
}
```

**Implications:**
```json
{
  "declarations": ["x: date", "flag: bool"],
  "constraints": [
    "(x.year == 2024) -> (flag == True)"
  ]
}
```

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

## Solver Approaches

DateSMT provides multiple solver approaches, each available in both integer and bitvector implementations:

- **naive** - Direct encoding of date arithmetic
- **epoch_days** - Convert dates to days since epoch (recommended, fast)
- **hybrid** - Hybrid approach combining multiple encodings
- **alpha_beta** - Alpha-beta encoding for optimized arithmetic
- **alpha_beta_table** - Table-based alpha-beta encoding

For most use cases, the default `epoch_days` approach with `int` implementation provides the best performance.

## Repository Structure

- `datesmt/` - Core library
  - `api.py` - DateSMTBuilder unified API
  - `solver.py` - High-level solve() function
  - `constraint_parser.py` - Constraint parsing and code generation
  - `core.py` - Date and Period data structures
  - `symbolic_int/` - Integer-based backends (naive, epoch_days, hybrid, alpha_beta, alpha_beta_table)
  - `symbolic_bitvector/` - Bitvector-based backends (naive, epoch_days, hybrid, alpha_beta, alpha_beta_table)
- `bin/` - Command-line interface
  - `datesmt.py` - CLI tool
- `tests/` - Test suite (see `tests/README.md` for details)
- `docs/` - Technical documentation
- `dataset/` - Benchmark generation and testing tools
  - `grammar_constraints/` - Grammar-based constraint generation
  - `llm_constraints/` - LLM-based constraint generation
  - `legal_doc_constraints/` - Real-world legal document constraints
  - `run_benchmarks.py` - Benchmark runner
- `requirements/` - Python dependencies

## Usage

### Python API

```python
import datesmt

# Basic usage
result = datesmt.solve(
    constraints=["x >= Date(2000,1,1)", "x < Date(2000,12,31)"],
    declarations=["x: date"]
)

# JSON format
result = datesmt.solve({
    "declarations": ["x: date", "y: date", "n: int"],
    "constraints": [
        "x >= Date(2024,1,1)",
        "y == x + Period(1,0,0)",
        "n > 5"
    ]
})

# Choose solver approach and implementation
result = datesmt.solve(
    constraints={...},
    approach="hybrid",           # naive, epoch_days, hybrid, alpha_beta, alpha_beta_table
    implementation="bitvector",  # int or bitvector
    timeout_ms=600000           # 10 minutes
)
```

### Command-Line Interface

```bash
# Read from stdin
python bin/datesmt.py < constraints.json

# Read from file
python bin/datesmt.py --file constraints.json

# Options
python bin/datesmt.py --approach hybrid --implementation bitvector < constraints.json
python bin/datesmt.py --output json < constraints.json
python bin/datesmt.py --quiet < constraints.json
python bin/datesmt.py --help
```

For comprehensive documentation, see [USAGE.md](USAGE.md).

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

## Benchmarks

Run benchmarks to compare different solver approaches:

```bash
# Run all benchmarks
python dataset/run_benchmarks.py --input dataset/grammar_constraints/benchmarks/constraints.json

# Run with specific approach
python dataset/run_benchmarks.py --input constraints.json --approach epoch_days --implementation int

# See all options
python dataset/run_benchmarks.py --help
```

The repository includes several benchmark datasets:
- **Grammar-based**: Automatically generated constraints following a grammar
- **LLM-based**: Constraints generated using language models
- **Legal documents**: Real-world constraints extracted from legal documents

## Development

### Pre-commit Hooks
This project uses pre-commit hooks to ensure code quality. Install and set up.

### CI/CD Pipeline
- **Trigger**: On each push to `dev` branch
- **Coverage**: Automatically builds coverage site and commits to `docs/` directory
- **GitHub Pages**: Serves coverage reports from `docs/` folder
- **Coverage Collection**: Uses `coverage.py` via `pytest-cov` for branch and line coverage
