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
python llm_generator/llm_client.py --num NUMBER --output FILE_NAME.json
```

### 3. Test Constraints

```bash
python llm_generator/test_template.py FILE_NAME.json --output-dir results
```

## Enhanced Output

The test template now provides:

- **Prediction accuracy** - How often the LLM correctly predicted SAT/UNSAT
- **Coverage analysis** - Breakdown by coverage tags
- **Approach comparison** - Baseline vs advanced with detailed metrics
- **Comprehensive reporting** - Success rates, timing, and accuracy per tag

## Requirements

- OpenAI/Anthropic API key
- DATE-SMT library
- Python packages