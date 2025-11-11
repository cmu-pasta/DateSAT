# Dataset Directory

This directory contains datasets, test constraints, and validation tools for the DATE-SMT project.

## Directory Structure

```
dataset/
├── validation.py              # Concrete validation module for verifying solver solutions
├── test_validation.py         # Unit tests for validation functionality
├── LLM_gen_constraints/       # LLM-based constraint generation and testing tools
│   └── README.md              # Detailed documentation for LLM constraint generation
└── law/                       # Constraints from legal documents
```

## Components

### Validation Module (`validation.py`)

The `validation.py` module provides concrete validation functionality to verify that symbolic solver solutions actually satisfy the constraints. This module is designed to work with any dataset.

**Key Features:**
- Works with any dataset by pointing to a results directory
- Supports multiple result file formats (`results_*.json` and `*_*.json` patterns)
- Reconstructs constraint code from constraint data when needed
- Validates SAT solutions using enumeration baseline as ground truth
- Records metrics for all approaches including enumeration baseline

**Validation Logic:**
The validation uses enumeration baseline as the ground truth and follows these rules:
1. **If all methods are SAT**: Validate all SAT solutions using enumeration baseline
2. **If some are SAT, some are UNSAT**: Check if SAT solutions are correct. If at least one SAT is correct, then UNSAT results are wrong
3. **If everything is UNSAT**: All approaches are correct
4. **If enumeration baseline is SAT but others are UNSAT**: The UNSAT approaches are wrong

**Key Functions:**
- `validate_solution_with_concrete()` - Validates a single solution against constraints
- `validate_results_with_concrete()` - Batch validation for all results in a directory
- `execute_constraint_code()` - Executes constraint code with concrete values

**Python API Usage:**
```python
from dataset.validation import validate_solution_with_concrete

constraint_data = {
    "constraints": ["x >= Date(2020, 1, 1)"],
    "coverage_tags": []
}
solution = {"x": "Date(2020, 3, 15)"}
is_valid, message, smtlib = validate_solution_with_concrete(constraint_data, solution)
```

**Command-Line Usage:**

The validation module can be used standalone to validate results from any dataset:

```bash
# Validate results from a dataset
python dataset/validation.py dataset/LLM_gen_constraints/results

# Validate results from another dataset (e.g., law constraints)
python dataset/validation.py dataset/law/results --output dataset/law/validation_results.json

# Specify custom output location
python dataset/validation.py path/to/results --output my_validation.json
```

The validation script will:
- Find all result JSON files in the specified directory (supports `results_*.json` and `*_*.json` patterns)
- Validate all SAT solutions against their constraints
- Generate a summary report with validation statistics
- Save results to `concrete_validation.json` (or custom path with `--output`)

**Expected Result File Format:**

Result files should contain JSON arrays of records, where each record has:
- `constraint_id`: Unique identifier for the constraint
- `approach`: The DATE-SMT approach used (e.g., "baseline", "epoch_days", "hybrid", "enumeration")
- `implementation`: The implementation type (e.g., "int", "bitvector", "baseline" for enumeration)
- `status`: Solver status ("sat", "unsat", "timeout", etc.)
- `solution`: Dictionary mapping variable names to solution values (for SAT results)
- `constraints`: Array of constraint strings (e.g., `["x >= Date(2020, 1, 1)"]`)
- `coverage_tags`: Optional array of coverage tags

**Baseline Approaches:**
- **enumeration**: Exhaustive enumeration baseline that checks all valid dates in the range [1900-03-01 to 2100-02-28]. Guaranteed to find a solution if one exists.

Example:
```json
[
  {
    "constraint_id": "test-1",
    "approach": "baseline",
    "implementation": "int",
    "status": "sat",
    "solution": {"x": "Date(2020, 3, 15)"},
    "constraints": ["x >= Date(2020, 1, 1)"],
    "coverage_tags": []
  }
]
```

### Validation Tests (`test_validation.py`)

Unit tests for the validation functionality covering:
- Date and period string parsing
- Simple constraint validation
- Constraints with periods
- Leap year edge cases
- Epoch boundary handling
- Invalid solution rejection

**Running Tests:**
```bash
pytest dataset/test_validation.py
```

## Usage Examples

### Validating Results from Any Dataset

```bash
# Basic usage - validate all results in a directory
python dataset/validation.py path/to/results

# With custom output location
python dataset/validation.py path/to/results --output validation_report.json

# View help
python dataset/validation.py --help
```

### Programmatic Usage

```python
from pathlib import Path
from dataset.validation import validate_results_with_concrete

# Validate all results in a directory
results_dir = Path("path/to/results")
validation_results = validate_results_with_concrete(results_dir)

# Access validation statistics
print(f"Total constraints: {validation_results['total_constraints']}")
print(f"Valid approaches: {validation_results['valid_approaches']}")
print(f"Validation rate: {validation_results['validation_rate']:.2%}")

# Access individual constraint results
for constraint_id, approaches in validation_results['constraint_results'].items():
    for approach, result in approaches.items():
        if result['valid']:
            print(f"{constraint_id} ({approach}): Valid ✓")
        else:
            print(f"{constraint_id} ({approach}): Invalid ✗ - {result['message']}")
```

## Additional Resources

- **LLM Constraint Generation**: See `LLM_gen_constraints/README.md` for detailed documentation on generating constraints with LLMs and running tests with `run_tests.py` (including the `--methods` option for selective method execution)
- **Main Project README**: See the root `README.md` for project overview and installation instructions
