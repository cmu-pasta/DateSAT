# DATE-SMT

A Python library for symbolic analysis of date-based computations using Z3.

## Overview

DATE-SMT provides both baseline and advanced implementations for expressing and solving date/time constraints using Z3. It converts DATE-SMT expressions into Z3 integer-only constraints for efficient symbolic analysis.

## Installation

```bash
# 1. Setup conda environment
conda create -y -n datesmt python=3.10
conda activate datesmt

# 2. Install dependencies
pip install -r requirements/core.txt

# 3. Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## Quick Start

```python
from datesmt.symbolic_api import solve_motivating_example

# Solve a date constraint problem
result = solve_motivating_example("advanced")
print(f"Status: {result['status']}")
if result['status'] == 'sat':
    print(f"Solution: {result['dates']}")
```

## Core Components

### Date/Period Classes (`datesmt/core.py`)
- **Unified**: Single Date/Period class with year/month/day representation
- **Epoch Support**: Built-in epoch conversion methods for efficient constraint solving
- **Focus**: Constraint translation, not arithmetic operations

### Symbolic Constraint Solving (`datesmt/`)
- **DateVar**: Symbolic date variables
- **PeriodVar**: Symbolic period variables
- **Z3 Integration**: Direct constraint translation to Z3

### Arithmetic Operations (`arithmetic/`)
- **Concrete Operations**: Date arithmetic, comparison, period operations
- **Purpose**: Testing and development, not core DATE-SMT functionality
- **Separate Module**: Keeps core library focused on constraint solving

## Testing

The project includes a comprehensive test suite to validate both baseline and advanced implementations:

### Running Tests

```bash
# Run all tests
python tests/test_runner.py

# Run specific test categories
python tests/test_epoch_conversion.py    # Epoch conversion tests
python tests/test_symbolic_api.py       # Symbolic API tests
python tests/comparison.py              # Comparison tests

# Run examples and demonstrations
python tests/run_all_examples.py        # Examples without formal tests
```

### Available Tests

1. **Epoch Conversion Tests** (`test_epoch_conversion.py`)
   - Tests bidirectional conversion between dates and epoch days
   - Validates leap year handling and edge cases
   - Ensures round-trip conversion accuracy

2. **Symbolic API Tests** (`test_symbolic_api.py`)
   - Tests the unified DateSMTBuilder API
   - Validates constraint solving for both approaches
   - Tests motivating example and constraint examples
   - Verifies approach comparison functionality

3. **Comparison Tests** (`comparison.py`)
   - Performance comparison between baseline and advanced approaches
   - Semantic equivalence validation
   - Comprehensive test suite for Date/Period classes

4. **Examples and Demonstrations** (`run_all_examples.py`)
   - Demonstrates core functionality without formal testing
   - Shows motivating example solutions
   - Illustrates epoch conversion capabilities

### Test Structure

```
tests/
├── test_runner.py           # Main test runner
├── test_epoch_conversion.py # Epoch conversion tests
├── test_symbolic_api.py     # Symbolic API tests
├── comparison.py            # Comparison framework
├── run_all_examples.py      # Examples and demonstrations
└── test_epoch_conversion.py # Epoch conversion validation
```

## Research Context

This library implements the DATE-SMT framework from the research proposal for efficient symbolic analysis of date-based computations, addressing the constraint explosion problem in program analysis tools.

## Project Structure

```
Date-SMT/
├── datesmt/                    # Core DATE-SMT library
│   ├── __init__.py            # Package initialization
│   ├── core.py                 # Unified Date/Period classes
│   ├── core.py                 # Unified Date/Period classes
│   ├── core.py                 # Unified Date/Period classes
│   ├── symbolic_baseline.py   # Baseline Z3 constraint translation
│   ├── symbolic_advanced.py   # Advanced Z3 constraint translation
│   ├── symbolic_api.py        # Unified API
│   └── semantic_comparison.py # Result comparison utilities
├── arithmetic/                 # Arithmetic operations (testing/development)
│   ├── __init__.py
│   ├── baseline_arithmetic.py # Baseline arithmetic operations
│   └── advanced_arithmetic.py # Advanced arithmetic operations
├── tests/                      # Test suite
│   ├── test_runner.py         # Main test runner
│   ├── test_epoch_conversion.py # Epoch conversion tests
│   ├── test_symbolic_api.py   # Symbolic API tests
│   ├── comparison.py          # Comparison framework
│   └── run_all_examples.py    # Examples and demonstrations
└── requirements/               # Dependencies
    ├── core.txt               # Core dependencies
    └── dev.txt                # Development dependencies
```

## Key Design Principles

1. **Separation of Concerns**: Core constraint solving vs. arithmetic operations
2. **Dual Approaches**: Baseline and advanced implementations for validation
3. **Z3 Integration**: Direct translation to integer constraints
4. **Clean API**: Easy-to-use interface for constraint expression
5. **Research Focus**: Addresses constraint explosion in program analysis
