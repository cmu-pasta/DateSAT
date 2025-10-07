## Integration Tests: Constraint Datasets

This folder contains integration tests that run DATE-SMT against curated JSON constraint datasets stored in `tests/integration_tests/data/`.

### What's here
- `data/constraints1.json`, `data/constraints2.json`: Sample datasets of constraints
- `test_constraint_datasets.py`: Pytest suite that executes both datasets through the full pipeline and validates outputs

### Run all integration tests
```bash
pytest tests/integration_tests -m integration -q
```

### Run a specific test file
```bash
pytest tests/integration_tests/test_constraint_datasets.py -q
```

### Run a single test case
```bash
pytest tests/integration_tests/test_constraint_datasets.py::TestConstraintDatasets::test_constraints1_dataset -q
```

### Run directly via the runner (bypass pytest)
You can also execute a dataset directly using the runner used by the tests:
```bash
python tests/integration_tests/test_template.py tests/integration_tests/data/constraints1.json --output-dir results/constraint1
```
This writes a `results_*.json` report under the specified `--output-dir`.

### Add a new dataset
1. Drop your JSON file into `tests/integration_tests/data/` (e.g., `constraints_myset.json`).
2. To run it quickly without modifying tests:
   ```bash
   python tests/test_template.py tests/integration_tests/data/constraints_myset.json --output-dir results_myset
   ```
3. To include it in the pytest suite, add a new test similar to the existing ones in `test_constraint_datasets.py`.

### Notes
- No API keys are required to run the integration tests on existing JSON files.
- The tests write outputs to a temporary directory when run via pytest; when run directly, outputs go to the directory you pass with `--output-dir`.
