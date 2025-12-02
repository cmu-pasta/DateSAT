# Enhanced LLM Date Constraint Generator

A robust, coverage-oriented date constraint generation system for DATE-SMT with enhanced schema validation and comprehensive testing.

**Note:** All commands in this README assume you are running from the repository root directory.

## Architecture

The constraint generation system is split into two components:

- **`dataset/llm.py`**: Universal LLM client that handles API calls, provider detection (OpenAI/Anthropic), and JSON parsing/normalization. This module can be reused by any dataset generator.

- **`dataset/llm_constraints/generator/constraint_generator.py`**: Constraint-specific generator that contains the system prompt, validation logic, and generation workflows. This module uses the universal `llm.py` for LLM interactions.

This separation allows the LLM infrastructure to be reused across different dataset generators while keeping constraint-specific logic isolated.

## What's New

This enhanced version includes:

- **Coverage-oriented system prompt** with explicit schema, guardrails, and coverage tags
- **Robust JSON parsing** with automatic retry/repair for flaky LLM responses
- **Deterministic seeding** for reproducibility
- **Comprehensive coverage tags** for leap year boundaries, month/day contrasts, etc.
- **Multi-provider support** for OpenAI and Anthropic APIs with auto-detection
- **Batch generation** with configurable batch sizes for large constraint sets
- **Backward compatibility** with simple string-based constraint formats

## Enhanced Schema

Generated constraints follow this schema:

```json
{
  "id": "1",
  "description": "Leap year boundary test",
  "constraints": ["x >= Date(2000,2,28)", "x <= Date(2000,3,1)", "x != Date(2000,2,28)", "x != Date(2000,3,1)"],
  "coverage_tags": ["leap_year", "eom"]
}
```

Each constraint object contains:
- `id`: Unique identifier (auto-generated)
- `description`: Human-readable explanation of the constraint set
- `constraints`: Array of constraint strings (parseable by the constraint parser)
- `coverage_tags`: Array of tags indicating what edge cases are covered

## Coverage Tags

The system generates constraints covering:

- `leap_year` - Leap year edge cases (Feb 28/29)
- `eom` - End-of-month rollovers (30 vs 31 vs 28/29)
- `year_vs_days` - Year vs day contrasts (1 year vs 365/366 days)
- `month_vs_days` - Month vs day contrasts (+1 month vs +31 days)
- `chain_ops` - Chains of additions/subtractions
- `chain_ops_brackets` - Chains with brackets (e.g., `x - (Period(...) + Period(...))`)
- `ineq_window` - Inequality windows (SAT/UNSAT via tight/wide ranges)
- `multi_var` - Multi-variable relations

## Usage

### 1. Set up your API key

```bash
# Set Anthropic API key (preferred)
export ANTHROPIC_API_KEY="your-anthropic-key-here"

# Or set OpenAI API key
export OPENAI_API_KEY="your-openai-key-here"
```

The system auto-detects which provider to use. If both are set, Anthropic is preferred.

### 2. Generate Constraints

Basic usage:

```bash
python dataset/llm_constraints/generator/constraint_generator.py --output dataset/llm_constraints/constraints/1.json
```

Advanced options:

```bash
# Specify provider explicitly
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --provider anthropic

# Use a specific model
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --model gpt-4

# Pass API key directly (instead of environment variable)
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --api-key YOUR_KEY

# Generate constraints with specific coverage tags only
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --tags leap_year eom

# Generate constraints with multiple specific tags
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --tags chain_ops multi_var ineq_window

# Control the number of constraints per object (vary between min and max)
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --min-constraints 2 --max-constraints 6

# Generate all objects with the same number of constraints
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --exact-constraints 5

# Combine tag filtering with constraint count control
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --tags leap_year eom --min-constraints 3 --max-constraints 7
```

### Command Line Arguments

- `--num`: Number of constraint objects to generate (default: 10)
- `--output`: Output filename (default: `generated_constraints.json`)
- `--provider`: LLM provider - `openai`, `anthropic`, or `auto` (default: `auto`)
- `--model`: Specific model name (uses default for provider if not specified)
- `--api-key`: API key (overrides environment variable)
- `--tags`: Coverage tags to restrict generation to (space-separated). Valid tags: `leap_year`, `eom`, `year_vs_days`, `month_vs_days`, `chain_ops`, `chain_ops_brackets`, `ineq_window`, `multi_var`. Default: all tags allowed
- `--min-constraints`: Minimum number of constraints per constraint object (default: 1)
- `--max-constraints`: Maximum number of constraints per constraint object (default: 8)
- `--exact-constraints`: Exact number of constraints per constraint object. If set, overrides min/max (all objects will have this exact count)

## Tag Filtering

You can restrict the LLM to generate constraints with only specific coverage tags using the `--tags` argument. This is useful when you want to focus on particular edge cases or test scenarios.

**Example**: To generate only leap year and end-of-month constraints:
```bash
python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --tags leap_year eom
```

If `--tags` is not specified, the LLM will generate constraints with any combination of tags (default behavior).

## Constraint Count Control

By default, the system generates constraint objects with a **varied number of constraints** (between 1 and 8 per object) to ensure diversity. You can control this behavior:

- **Default behavior**: If no constraint count options are specified, each constraint object will have a different number of constraints (varying between 1 and 8). This ensures diversity in the generated dataset.

- **Min/Max range**: Use `--min-constraints` and `--max-constraints` to set a custom range. The system will generate objects with varying counts within this range.

  **Example**: Generate constraints with 3-7 constraints per object:
  ```bash
  python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --min-constraints 3 --max-constraints 7
  ```

- **Exact count**: Use `--exact-constraints` to make all objects have the same number of constraints. This overrides any min/max settings.

  **Example**: Generate all objects with exactly 5 constraints:
  ```bash
  python dataset/llm_constraints/generator/constraint_generator.py --num 10 --output dataset/llm_constraints/constraints/1.json --exact-constraints 5
  ```

## Combining Constraints

After generating multiple constraint files, you can combine them into a single file using the `combine_constraints.py` script:

```bash
# Combine all constraint files (excluding all_constraints.json) into all_constraints.json
python dataset/llm_constraints/generator/combine_constraints.py

# Specify custom directory and output file
python dataset/llm_constraints/generator/combine_constraints.py --constraints-dir dataset/llm_constraints/constraints --output dataset/llm_constraints/constraints/all_constraints.json
```

The script will:
- Find all JSON files in the constraints directory
- Exclude `all_constraints.json` itself (to avoid recursion)
- Combine all constraints into a single array
- Save the result as `all_constraints.json`

## Testing and Validation

### Running Constraint Tests (`run_tests.py`)

The `run_tests.py` script tests all constraints with multiple approaches:
- **Symbolic approaches**: baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table (with both int and bitvector implementations)
- **Baseline approaches**: enumeration (exhaustive enumeration)

**Basic Usage:**
```bash
# Test all constraints in a file with default settings
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json
```

**Command-Line Arguments:**
- `constraints_file` (required): Path to the JSON file containing constraints to test (relative to repository root)
- `--output-dir`: Output directory for results (default: `results`, relative to current working directory)
- `--timeout`: Timeout in milliseconds for each constraint (default: 10 minutes)
- `--methods`: Select specific methods to run (default: all methods). Can specify multiple methods.
  - Format options:
    - `approach_implementation` (e.g., `baseline_bitvector`, `epoch_days_int`)
    - `approach` (e.g., `baseline` - runs all implementations of that approach)
    - `implementation` (e.g., `bitvector` - runs all approaches with that implementation)
    - `enumeration` (baseline approach)
  - Examples: `--methods baseline_bitvector enumeration` or `--methods bitvector`
- `--analysis`: Enable analysis after constraint execution (default: enabled)
- `--no-analysis`: Skip analysis and only run constraint execution

**Examples:**
```bash
# Test all constraints with default settings (all methods)
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json

# Test constraints with custom output directory
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/1.json --output-dir dataset/llm_constraints/results/test1

# Test with custom timeout (30 seconds)
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --timeout 30000

# Run tests without analysis (faster, no validation)
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/1.json --no-analysis

# Run only specific methods: baseline_bitvector and enumeration
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --methods baseline_bitvector enumeration

# Run all bitvector implementations
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --methods bitvector

# Run baseline approach with both int and bitvector implementations
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --methods baseline

# Run multiple specific methods
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --methods baseline_int epoch_days_bitvector enumeration

# Test with all options
python dataset/llm_constraints/run_tests.py dataset/llm_constraints/constraints/all_constraints.json --output-dir dataset/llm_constraints/results/full_test --timeout 120000 --methods baseline_bitvector --analysis
```

**Output:**
The script generates:
- Individual result files for each approach: `{approach}_{implementation}_{timestamp}.json`
- SMT-LIB files for each constraint: `smt2/{constraint_id}_{approach}_{implementation}.smt2`
- Analysis summary (if analysis enabled): `checked_summary.json` containing:
  - Validation results using enumeration baseline as ground truth
  - Correctness verdicts for each approach
  - Metrics (execution time, SMT-LIB lines, etc.)
  - Summary statistics by approach

**What Gets Tested:**
By default, for each constraint, the script tests:
1. All symbolic approaches (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table)
2. Both implementations (int and bitvector) for each symbolic approach
3. The enumeration baseline approach

Use the `--methods` option to selectively run only specific methods, which can significantly reduce execution time for focused testing.

**Validation:**
The `dataset/validation.py` module provides concrete validation functionality to verify that symbolic solver solutions actually satisfy the constraints. It uses enumeration baseline as the ground truth for validation. This is used automatically by `run_tests.py` when analysis is enabled.

For more information on validation logic and workflow, see the dataset-level `README.md`:
- Validation workflow and usage
- Running validation unit tests
- Validation logic based on enumeration baseline

## Features

- **Automatic retry/repair**: Failed JSON parsing triggers automatic repair attempts
- **Batch generation**: Large constraint sets are generated in batches for reliability
- **Schema validation**: Ensures all generated constraints match the expected format
- **Tag filtering**: Restrict generation to specific coverage tags
- **Varied constraint counts**: By default, generates objects with different numbers of constraints (1-8) for diversity
- **Constraint count control**: Fine-tune the number of constraints per object with min/max/exact options
- **Constraint combining**: Merge multiple constraint files into one consolidated file
- **Debug output**: Failed generations save debug info to `_debug/` directory
