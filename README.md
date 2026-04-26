# DateSAT: A Framework for Solving Date and Period Constraints

[![CI Badge](https://github.com/cmu-pasta/DateSAT/actions/workflows/ci.yml/badge.svg)](https://github.com/cmu-pasta/DateSAT/actions/workflows/ci.yml)
[![Coverage Badge](https://pastalab.org/DateSAT/badge.svg)](https://pastalab.org/DateSAT/)

## Overview

DateSAT provides implementations to multiple encodings strategies for solving date and calendar period constraints. It encodes DateSAT constraints into Z3 constraints (expressed through integer or bitvector constraints) for efficient symbolic analysis.

The library offers both a high-level Python API and a command-line interface for solving date constraints with support for:
- Date and period arithmetic
- Date, Integer and Boolean variables
- Complex boolean expressions with `&&`, `||`, `!`, and implications (`->`)
- Date component access (`.year`, `.month`, `.day`)
- Multiple solver approaches optimized for different use cases

## Supported Ranges

In the implementation, we apply the below supported ranges on Date and Period. 
Note that a bound is not required to ensure decidability.
Please refer to the paper (Section 3.3) for more details.

### Date Range

All `Date` objects must fall within the following range:
- **Minimum**: 1900-03-01
- **Maximum**: 2100-02-28

Dates outside this range will raise a `ValueError` during construction.

### Period Range

All `Period` objects must fall within the following bounds (based on the date range):
- **Years**: ±200 (maximum absolute value)
- **Months**: ±2400 (maximum absolute value, equivalent to ±200 years)
- **Days**: ±73048 (maximum absolute value, equivalent to the full date range span)

Periods exceeding these bounds will raise a `ValueError` during construction.

## Quick Start

### Installation

```bash
# 1. Setup conda environment
conda create -y -n datesat python=3.10
conda activate datesat

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

### Python API

```python
import datesat

# Solve date constraints
result = datesat.solve({
    "declarations": ["x: date", "y: date"],
    "constraints": [
        "x >= Date(2024,1,1)",
        "y == x + Period(0,1,0)",
        "x.month == 6"
    ]
})

if result["status"] == "sat":
    print(f"x = {result['dates']['x']}")
    print(f"y = {result['dates']['y']}")
```

```python
import datesat

# 1. Basic Usage (List of constraints)
result_basic = datesat.solve(
    constraints=["x >= Date(2000,1,1)", "x < Date(2000,12,31)"],
    declarations=["x: date"]
)

# 2. JSON/Dictionary Format
# This is the standard input format for DATESAT [cite: 153, 953]
input_data = {
    "declarations": ["x: date", "y: date", "n: int"],
    "constraints": [
        "x >= Date(2024,1,1)",
        "y == x + Period(1,0,0)",
        "n > 5"
    ]
}
result_json = datesat.solve(input_data)

# 3. Specific Strategy Selection
# Replace {...} with the actual data variable
result_optimized = datesat.solve(
    constraints=input_data,      # Use the dictionary defined above
    approach="alpha_beta_table", # Recommended: provides a median 2.73x speedup [cite: 146, 913]
    implementation="int",        # Choose 'int' or 'bitvector' [cite: 146, 972]
    timeout_ms=600000            # 10 minutes [cite: 878]
)

print(result_optimized)
```

### Command-Line Interface

```bash
# From stdin
echo '{"declarations":["x: date"],"constraints":["x >= Date(2024,1,1)"]}' | python bin/datesat_cli.py

# From file
python bin/datesat_cli.py --file constraints.json

# With options
python bin/datesat_cli.py --approach hybrid --implementation bitvector --output json < constraints.json
python bin/datesat_cli.py --help
```

### MCP Server (for AI Agents)

DateSAT includes an MCP (Model Context Protocol) server that allows AI agents to solve date constraints:

```bash
# Start MCP server on default port (8000)
python bin/datesat_mcp.py

# Start on custom port
python bin/datesat_mcp.py --port 3000
```

The server exposes a `solve` tool at `http://localhost:<port>/sse` that AI agents can use to solve date constraints programmatically.

See [USAGE.md](USAGE.md) for comprehensive documentation and examples.

## Constraint Format

Constraints are specified in JSON format with variable declarations and constraint expressions.

### Basic Format

```json
{
  "declarations": ["variable_name: type", ...],
  "constraints": ["constraint_expression", ...]
}
```

**Variable Types:**
- `date` - Date variable
- `int` - Integer variable
- `bool` - Boolean variable

**All constraints in the list are ANDed together.**

### Constraint Language

**Date and Period Constructors:**
- `Date(year, month, day)` - e.g., `Date(2024, 6, 15)`
- `Period(years, months, days)` - e.g., `Period(1, 6, 0)`

**Date Arithmetic:**
- `date + period`, `date - period`
- `period + period`, `period - period`
- `int * period`

*Note: `date - date` is not supported.*

**Date Comparisons:**
- `==`, `!=`, `<`, `<=`, `>`, `>=`

**Date Components:**
- `date.year`, `date.month`, `date.day`

**Boolean Operators:**
- `&&` (AND), `||` (OR), `!` (NOT)
- `->` (implication)

### Examples

**Simple constraints:**
```json
{
  "declarations": ["x: date"],
  "constraints": [
    "x >= Date(2000,2,28)",
    "x <= Date(2000,3,1)"
  ]
}
```

**Boolean operators:**
```json
{
  "declarations": ["x: date"],
  "constraints": [
    "x >= Date(2000,2,28) || x <= Date(2000,2,29)",
    "x != Date(2000,3,1)"
  ]
}
```

**Date components and integer variables:**
```json
{
  "declarations": ["x: date", "n: int"],
  "constraints": [
    "x.year == 2024",
    "n > 5",
    "n < 10"
  ]
}
```

**Implications:**
```json
{
  "declarations": ["x: date", "flag: bool"],
  "constraints": [
    "(x.year == 2024) -> (flag == True)"
  ]
}
```

## Testing

We provide a thorough testing set to aid future DateSAT solver implementation. See `tests/README.md` for more details.

## Development

### CI/CD Pipeline
- **Trigger**: On each push to `dev` branch
- **Coverage**: Automatically builds coverage site and commits to `docs/` directory
- **GitHub Pages**: Serves coverage reports from `docs/` folder
- **Coverage Collection**: Uses `coverage.py` via `pytest-cov` for branch and line coverage
