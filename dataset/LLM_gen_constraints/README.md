# Enhanced LLM Date Constraint Generator

A robust, coverage-oriented date constraint generation system for DATE-SMT with enhanced schema validation and comprehensive testing.

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
python dataset/LLM_gen_constraints/generator/llm_client.py --output dataset/LLM_gen_constraints/constraints/1.json
```

Advanced options:

```bash
# Specify provider explicitly
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --provider anthropic

# Use a specific model
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --model gpt-4

# Pass API key directly (instead of environment variable)
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --api-key YOUR_KEY

# Generate constraints with specific coverage tags only
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --tags leap_year eom

# Generate constraints with multiple specific tags
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --tags chain_ops multi_var ineq_window

# Control the number of constraints per object (vary between min and max)
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --min-constraints 2 --max-constraints 6

# Generate all objects with the same number of constraints
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --exact-constraints 5

# Combine tag filtering with constraint count control
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --output dataset/LLM_gen_constraints/constraints/1.json --tags leap_year eom --min-constraints 3 --max-constraints 7
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
python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --tags leap_year eom
```

If `--tags` is not specified, the LLM will generate constraints with any combination of tags (default behavior).

## Constraint Count Control

By default, the system generates constraint objects with a **varied number of constraints** (between 1 and 8 per object) to ensure diversity. You can control this behavior:

- **Default behavior**: If no constraint count options are specified, each constraint object will have a different number of constraints (varying between 1 and 8). This ensures diversity in the generated dataset.

- **Min/Max range**: Use `--min-constraints` and `--max-constraints` to set a custom range. The system will generate objects with varying counts within this range.

  **Example**: Generate constraints with 3-7 constraints per object:
  ```bash
  python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --min-constraints 3 --max-constraints 7
  ```

- **Exact count**: Use `--exact-constraints` to make all objects have the same number of constraints. This overrides any min/max settings.

  **Example**: Generate all objects with exactly 5 constraints:
  ```bash
  python dataset/LLM_gen_constraints/generator/llm_client.py --num 10 --exact-constraints 5
  ```

## Combining Constraints

After generating multiple constraint files, you can combine them into a single file using the `combine_constraints.py` script:

```bash
# Combine all constraint files (excluding all_constraints.json) into all_constraints.json
python dataset/LLM_gen_constraints/generator/combine_constraints.py

# Specify custom directory and output file
python dataset/LLM_gen_constraints/generator/combine_constraints.py --constraints-dir ../constraints --output ../constraints/all_constraints.json
```

The script will:
- Find all JSON files in the constraints directory
- Exclude `all_constraints.json` itself (to avoid recursion)
- Combine all constraints into a single array
- Save the result as `all_constraints.json`

## Testing and Validation

### Running Constraint Tests

Use `run_tests.py` to execute constraints against all DATE-SMT approaches and implementations:

```bash
# Run tests with analysis (default)
python dataset/LLM_gen_constraints/run_tests.py dataset/LLM_gen_constraints/constraints/all_constraints.json --output-dir dataset/LLM_gen_constraints/results

# Run tests without analysis
python dataset/LLM_gen_constraints/run_tests.py dataset/LLM_gen_constraints/constraints/all_constraints.json --output-dir dataset/LLM_gen_constraints/results --no-analysis

# Set custom timeout (in milliseconds)
python dataset/LLM_gen_constraints/run_tests.py dataset/LLM_gen_constraints/constraints/all_constraints.json --output-dir dataset/LLM_gen_constraints/results --timeout 120000
```

The script will:
- Execute each constraint with all approaches (baseline, epoch_days, hybrid, alpha_beta, alpha_beta_table)
- Test both implementations (int and bitvector)
- Generate SMT-LIB files for each constraint
- Validate SAT solutions using concrete validation (if analysis is enabled)
- Generate summary statistics and analysis reports

### Validation

The `validation.py` module provides concrete validation functionality to verify that symbolic solver solutions actually satisfy the constraints. This is used automatically by `run_tests.py` when analysis is enabled.

### Running Validation Tests

Use `test_validation.py` to run unit tests for the validation functionality:

```bash
# Run validation tests
pytest dataset/LLM_gen_constraints/test_validation.py
```

## Features

- **Automatic retry/repair**: Failed JSON parsing triggers automatic repair attempts
- **Batch generation**: Large constraint sets are generated in batches for reliability
- **Schema validation**: Ensures all generated constraints match the expected format
- **Tag filtering**: Restrict generation to specific coverage tags
- **Varied constraint counts**: By default, generates objects with different numbers of constraints (1-8) for diversity
- **Constraint count control**: Fine-tune the number of constraints per object with min/max/exact options
- **Constraint combining**: Merge multiple constraint files into one consolidated file
- **Debug output**: Failed generations save debug info to `_debug/` directory
