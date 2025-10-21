## Integration Tests: Constraint Datasets

This folder contains integration tests that run DATE-SMT against curated JSON constraint datasets stored in `tests/integration_tests/data/`.

### What's here
- `data/constraints1.json`, `data/constraints2.json`: Sample datasets of constraints
- `run_tests.py`: Unified test runner that combines constraint execution and analysis
- `validation.py`: Concrete validation module for solution verification
- `test_validation.py`: Unit tests for concrete validation functionality

### Run all integration tests
```bash
pytest tests/integration_tests -m integration -q
```

### Run a single test case
```bash
pytest tests/integration_tests/test_constraint_datasets.py::TestConstraintDatasets::test_constraints1_dataset -q
```

### Run directly via the unified test runner
You can execute a dataset directly using the unified test runner that combines constraint execution and analysis:

```bash
# Run with both execution and analysis (default)
python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints1.json --output-dir tests/integration_tests/results/constraint1

# Run only constraint execution (skip analysis)
python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints1.json --output-dir tests/integration_tests/results/constraint1 --no-analysis

# Run with custom timeout
python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints1.json --output-dir tests/integration_tests/results/constraint1 --timeout 30000
```

What it does:
- **Constraint Execution**: Runs all constraints through all approaches (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table) and implementations (int, bitvector)
- **Analysis** (default): Validates SAT solutions using concrete implementation validation
- **SMT-LIB Generation**: Saves SMT-LIB files for each constraint/approach combination
- **Results**: Writes `results_*.json` reports and `checked_summary.json` under the specified `--output-dir`

Output schema highlights (`checked_summary.json`):
- `counts_by_approach`: per-method tallies of `{correct, wrong, error, timeout}`
- `by_constraint[i].verdicts_by_approach`: per-method verdicts only (no aggregate verdict)
- `by_constraint[i].unsat_consensus`: `true` if all methods reported `unsat`
- `metrics`: Performance metrics including SMT-LIB line counts and execution times

### Command-line Options
```bash
python tests/integration_tests/run_tests.py [OPTIONS] constraints_file

Options:
  --output-dir OUTPUT_DIR    Output directory for results (default: results)
  --timeout TIMEOUT         Timeout in milliseconds (default: 60000)
  --analysis                Run analysis after constraint execution (default: True)
  --no-analysis             Skip analysis and only run constraint execution
  -h, --help               Show help message
```

### Concrete Validation
The integration tests use concrete validation instead of Z3-based validation:

- **`validation.py`**: Standalone concrete validation module
- **`test_validation.py`**: Unit tests for concrete validation functionality
- **`run_tests.py`**: Automatically validates SAT solutions with concrete implementation
- **No Z3 rebuilding needed**: Uses Python's datetime library for direct validation

Concrete validation benefits:
- **Faster**: Uses Python's datetime library instead of SMT solving
- **More reliable**: No complex constraint rebuilding or Z3 solver issues
- **Simpler**: Direct validation of solution correctness
- **Better debugging**: Clear error messages and validation results

### Add a new dataset
1. Drop your JSON file into `tests/integration_tests/data/` (e.g., `constraints_myset.json`).
2. To run it quickly without modifying tests:
   ```bash
   python tests/integration_tests/run_tests.py tests/integration_tests/data/constraints_myset.json --output-dir results_myset
   ```
3. To include it in the pytest suite, add a new test similar to the existing ones in `test_constraint_datasets.py`.

### Notes
- No API keys are required to run the integration tests on existing JSON files.
- The tests write outputs to a temporary directory when run via pytest; when run directly, outputs go to the directory you pass with `--output-dir`.
