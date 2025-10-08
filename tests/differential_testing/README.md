# Differential Testing

This folder contains comprehensive differential tests that compare the baseline and epoch_days implementations to ensure they produce identical results.

## Test File

### `test_solver_equivalence.py`
**Purpose**: Comprehensive differential testing of all solver functionality

**Core Solver Tests**:
- `test_sat_unsat_parity_simple_date_constraints` (8 test cases): SAT/UNSAT parity for various constraints
- `test_model_agreement_when_sat` (3 test cases): Model solution agreement when satisfiable
- `test_period_arithmetic_equivalence` (4 test cases): Period arithmetic result equivalence
- `test_epoch_rebasing_consistency` (1 test case): Epoch rebasing consistency
- `test_random_constraint_equivalence` (10 test cases): Random constraint generation and testing

**Date Arithmetic Edge Cases Tests**:
- `test_year_jumps_across_leap_years` (9 test cases): Feb 29 handling across years
- `test_month_jumps_with_varying_lengths` (14 test cases): Month boundary transitions
- `test_mixed_periods_crossing_feb` (8 test cases): Mixed periods crossing February
- `test_negative_periods_edge_cases` (7 test cases): Negative period operations
- `test_four_year_cycle_math` (6 test cases): Leap year cycle validation
- `test_month_lookup_path_validation` (12 test cases): All months with maximum days
- `test_edge_case_solver_constraints` (1 test case): Complex edge case with solver

**Focus**: Complete solver behavior testing including core functionality and edge cases

## Test Count Summary

- **Total test functions**: 12
- **Total individual test cases**: ~82 (all parametrized)
- **Coverage**: Complete solver behavior + comprehensive date arithmetic edge cases

## Running Tests

```bash
# Run all differential tests
pytest tests/differential_testing/

# Run the comprehensive test file
pytest tests/differential_testing/test_solver_equivalence.py

# Run with verbose output to see individual test cases
pytest -v tests/differential_testing/

# Run specific test categories
pytest -k "test_sat_unsat" tests/differential_testing/
pytest -k "test_year_jumps" tests/differential_testing/
```

## Test Philosophy

These are **differential tests** - they compare two implementations against each other rather than against ground truth. This approach:

1. **Validates equivalence**: Ensures both implementations produce identical results
2. **No ground truth needed**: Doesn't require manually calculated expected values
3. **Catches regressions**: Any divergence between implementations indicates a problem
4. **Comprehensive coverage**: Tests both normal cases and edge cases
