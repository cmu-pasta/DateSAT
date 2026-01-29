# DateSATBench's LLM-Synthesized Dataset Generator

## Usage

### 1. Set up your API key

```bash
# Set Anthropic API key (preferred: used for the existing dataset)
export ANTHROPIC_API_KEY="your-anthropic-key-here"

# Or set OpenAI API key
export OPENAI_API_KEY="your-openai-key-here"
```

The system auto-detects which provider to use. If both are set, Anthropic is preferred.

### 2. Generate Constraints

Basic usage:

```bash
# Generate 10 constraints
python datesatbench/llm_constraints/generator/constraint_generator.py --num 10 --output datesatbench/llm_constraints/constraints/1.json
```

### Command Line Arguments

- `--num`: Number of constraints clause to generate (default: 10)
- `--output`: Output filename (default: `generated_constraints.json`)
- `--provider`: LLM provider - `openai`, `anthropic`, or `auto` (default: `auto`)
- `--tags`: Coverage tags to restrict generation to (space-separated). See below for valid tags. Default: all tags allowed
- `--min-constraints`: Minimum number of constraints per constraints clause (default: 1)
- `--max-constraints`: Maximum number of constraints per constraints clause (default: 8)
- `--exact-constraints`: Exact number of constraints per constraints clause. If set, overrides min/max (all clause will have this exact count of constraints)

## Tag Filtering

You can restrict the LLM to generate constraints with only specific coverage tags using the `--tags` argument. This is useful when you want to focus on particular edge cases or test scenarios.

**Example**: To generate only leap year and end-of-month constraints:
```bash
python datesatbench/llm_constraints/generator/constraint_generator.py --num 10 --output datesatbench/llm_constraints/constraints/1.json --tags year_vs_days
```

If `--tags` is not specified, the LLM will generate constraints with any combination of tags (default behavior).

## Constraint Count Control

By default, the system generates constraint objects with a **varied number of constraints** (between 1 and 8 per object) to ensure diversity. You can control this behavior:

- **Default behavior**: If no constraint count options are specified, each constraint object will have a different number of constraints (varying between 1 and 8). This ensures diversity in the generated datesatbench.

- **Min/Max range**: Use `--min-constraints` and `--max-constraints` to set a custom range. The system will generate objects with varying counts within this range.

  **Example**: Generate constraints with 3-7 constraints per object:
  ```bash
  python datesatbench/llm_constraints/generator/constraint_generator.py --num 10 --output datesatbench/llm_constraints/constraints/1.json --min-constraints 3 --max-constraints 7
  ```

- **Exact count**: Use `--exact-constraints` to make all objects have the same number of constraints. This overrides any min/max settings.

  **Example**: Generate all objects with exactly 5 constraints:
  ```bash
  python datesatbench/llm_constraints/generator/constraint_generator.py --num 10 --output datesatbench/llm_constraints/constraints/1.json --exact-constraints 5
  ```

## Combining Constraints

After generating multiple constraint files, you can combine them into a single file using the `combine_constraints.py` script:

```bash
# Combine all constraint files (excluding all_constraints.json) into all_constraints.json
python datesatbench/llm_constraints/generator/combine_constraints.py

# Specify custom directory and output file
python datesatbench/llm_constraints/generator/combine_constraints.py --constraints-dir datesatbench/llm_constraints/constraints --output datesatbench/llm_constraints/constraints/all_constraints.json
```

The script will:
- Find all JSON files in the constraints directory
- Exclude `all_constraints.json` itself (to avoid recursion)
- Combine all constraints into a single array
- Save the result as `all_constraints.json`

## Output Schema

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

1) Year vs day contrasts (1 year ≠ 365/366 days) → tag: "year_vs_days"
2) Month vs day contrasts (+1 month ≠ +31 days) → tag: "month_vs_days"
3) Symbolic variables in date expressions like Date(x, 1, 2) or Date(x+1, 2, 1) → tag: "symbolic_date_vars"
4) Property access on date variables like x.year, x.month, x.day → tag: "property_access"
5) Use of logical operators like &&, ||, ! → tag: "logical_operators"
