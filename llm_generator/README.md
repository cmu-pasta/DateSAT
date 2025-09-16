# Enhanced LLM Date Constraint Generator

A robust, coverage-oriented date constraint generation system for DATE-SMT with enhanced schema validation and comprehensive testing.

## What's New

This enhanced version includes:

- **Coverage-oriented system prompt** with explicit schema, guardrails, and coverage tags
- **Robust JSON parsing** with automatic retry/repair for flaky LLM responses
- **Deterministic seeding** for reproducibility
- **Comprehensive coverage tags** for leap year boundaries, month/day contrasts, etc.
- **SAT/UNSAT prediction accuracy** tracking
- **Coverage analysis** to ensure diverse constraint types

## Enhanced Schema

Generated constraints now include:

```json
{
  "id": "constraint_1",
  "description": "Leap year boundary test",
  "constraint_code": "builder.add_constraint(x >= Date(2024, 2, 28), 'x >= 2024-02-28')\nbuilder.add_constraint(x <= Date(2024, 3, 1), 'x <= 2024-03-01')",
  "variables": ["x"],
  "coverage_tags": ["leap_boundary"],
  "expected_satisfiable": true
}
```

## Coverage Tags

The system generates constraints covering:

- `leap_boundary` - Leap year edge cases (Feb 28/29)
- `eom` - End-of-month rollovers (30 vs 31 vs 28/29)
- `year_vs_days` - Year vs day contrasts (1 year vs 365/366 days)
- `month_vs_days` - Month vs day contrasts (+1 month vs +31 days)
- `chain_add` - Chains of additions/subtractions
- `ineq_window` - Inequality windows (SAT/UNSAT via tight/wide ranges)
- `multi_var` - Multi-variable relations

## Usage

### 1. Set up your API key

```bash
# Set Anthropic API key
export ANTHROPIC_API_KEY="your-anthropic-key-here"

# Or set OpenAI API key
export OPENAI_API_KEY="your-openai-key-here"
```

### 2. Generate Constraints

```bash
python llm_generator/llm_client.py --num 8 --output enhanced_constraints.json
```

### 3. Test Constraints

```bash
python llm_generator/test_template.py enhanced_constraints.json --output-dir results
```

### 4. Complete Workflow

```bash
# Generate and test
python llm_generator/llm_client.py --num 10 --output constraints.json
python llm_generator/test_template.py constraints.json --output-dir test_results
```

## Enhanced Output

The test template now provides:

- **Prediction accuracy** - How often the LLM correctly predicted SAT/UNSAT
- **Coverage analysis** - Breakdown by coverage tags
- **Approach comparison** - Baseline vs advanced with detailed metrics
- **Comprehensive reporting** - Success rates, timing, and accuracy per tag

## Key Improvements

1. **Robust Generation**: Automatic retry/repair for malformed JSON responses
2. **Coverage Focus**: Ensures diverse constraint types are generated
3. **Validation**: Strict schema validation with helpful error messages
4. **Analysis**: Detailed coverage and accuracy analysis
5. **Reproducibility**: Deterministic seeding for consistent results

## Example Output

```
=== Testing constraint_1 (ADVANCED) ===
Description: Leap year boundary test
Coverage tags: leap_boundary
Expected satisfiable: true
Constraint: builder.add_constraint(x >= Date(2024, 2, 28), 'x >= 2024-02-28')...
✅ Solution found:
  x = Date(2024, 2, 28)
✅ Prediction correct (expected true, got true)

COVERAGE ANALYSIS
================
Coverage tags found: chain_add, eom, ineq_window, leap_boundary, month_vs_days, multi_var, year_vs_days

leap_boundary: 2 constraints
  baseline: 2/2 successful
  advanced: 2/2 successful
```

## Requirements

- OpenAI API key (for real generation)
- DATE-SMT library
- Python packages: `openai`, `json`, `re`, `os`, `time`, `datetime`

This enhanced version provides much more reliable and comprehensive constraint generation, perfect for building a high-quality constraints dataset for DATE-SMT research.
