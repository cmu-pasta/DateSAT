# DateSAT Usage Guide

## Python API

### Basic Usage

```python
import datesat

# Simple constraint solving
result = datesat.solve(
    constraints=["x >= Date(2000,1,1)", "x < Date(2000,12,31)"],
    declarations=["x: date"]
)

if result["status"] == "sat":
    print(f"Solution found: {result['dates']['x']}")
```

### JSON Format

```python
import datesat

# Using JSON format (same as CLI input)
result = datesat.solve({
    "declarations": ["x: date", "y: date"],
    "constraints": [
        "x >= Date(2000,1,1)",
        "y == x + Period(0,1,0)"
    ]
})

print(f"Status: {result['status']}")
print(f"Dates: {result['dates']}")
print(f"Execution time: {result['execution_time']:.3f}s")
```

### With Integer and Boolean Variables

```python
import datesat

result = datesat.solve({
    "declarations": ["x: date", "n: int", "flag: bool"],
    "constraints": [
        "x.year == 2000 + n",
        "n > 5",
        "n < 10",
        "flag == (n > 7)"
    ]
})

if result["status"] == "sat":
    print(f"Date: {result['dates']['x']}")
    print(f"Integer: {result['ints']['n']}")
    print(f"Boolean: {result['bools']['flag']}")
```

### Choosing Solver Approach

```python
import datesat

# Use different solver approaches and implementations
result = datesat.solve(
    constraints={...},           # replace ... with actual constraints
    approach="hybrid",           # simple, epoch_days, hybrid, alpha_beta, alpha_beta_table
    implementation="bitvector",  # int or bitvector
    timeout_ms=600000,          # 10 minutes
    verbose=True                # Print solver output
)
```

### Load from JSON File

```python
import datesat
import json

with open('constraints.json') as f:
    constraint_data = json.load(f)

result = datesat.solve(constraint_data)
```

## Command-Line Interface

### Basic Usage

```bash
# Read from stdin
./bin/datesat_cli.py < constraints.json

# Or using cat
cat constraints.json | python bin/datesat_cli.py

# Read from file
python bin/datesat_cli.py --file constraints.json
```

### Input Format

Create a JSON file with declarations and constraints:

```json
{
  "declarations": ["x: date", "y: date", "n: int"],
  "constraints": [
    "x >= Date(2000,1,1)",
    "y == x + Period(0,1,0)",
    "x.year == 2000 + n",
    "n > 5",
    "n < 10"
  ]
}
```

### CLI Options

```bash
# Choose solver approach and implementation
python bin/datesat_cli.py --approach hybrid --implementation bitvector < constraints.json

# Get JSON output instead of human-readable format
python bin/datesat_cli.py --output json < constraints.json

# Set timeout (in milliseconds)
python bin/datesat_cli.py --timeout 300000 < constraints.json  # 5 minutes

# Quiet mode (suppress solver output)
python bin/datesat_cli.py --quiet < constraints.json

# Show help
python bin/datesat_cli.py --help
```

### CLI Examples

```bash
# Simple constraint
echo '{"declarations":["x: date"],"constraints":["x >= Date(2000,1,1)"]}' | python bin/datesat_cli.py --quiet

# With file input and JSON output
python bin/datesat_cli.py --file constraints.json --output json

# Using hybrid approach with bitvector implementation
python bin/datesat_cli.py --approach hybrid --implementation bitvector --file constraints.json
```

## MCP Server (for AI Agents)

DateSAT includes an MCP (Model Context Protocol) server that allows AI agents to solve date constraints programmatically.

### Starting the Server

```bash
# Start on default port (8000)
python bin/datesat_mcp.py

# Start on custom port
python bin/datesat_mcp.py --port 3000

# Listen on all network interfaces
python bin/datesat_mcp.py --host 0.0.0.0 --port 8080

# Enable auto-reload for development
python bin/datesat_mcp.py --reload
```

### MCP Endpoint

Once running, the MCP SSE endpoint is available at:
```
http://<host>:<port>/sse
```

AI agents connect to this endpoint to discover and call the `solve` tool.

### The `solve` Tool

The MCP server exposes a single `solve` tool with the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `declarations` | `list[str]` | required | Variable declarations (e.g., `["x: Date", "n: int"]`) |
| `constraints` | `list[str]` | required | Constraint expressions to satisfy |
| `approach` | `str` | `"epoch_days"` | Solver approach: `simple`, `epoch_days`, `hybrid`, `alpha_beta`, `alpha_beta_table` |
| `implementation` | `str` | `"int"` | Implementation type: `int` or `bitvector` |
| `timeout_ms` | `int` | `600000` | Solver timeout in milliseconds |

### Response Format

The `solve` tool returns a JSON object with:

```json
{
  "status": "sat|unsat|timeout|error",
  "dates": {"x": "Date(2024, 6, 1)", ...},
  "ints": {"n": 5, ...},
  "bools": {"flag": true, ...},
  "execution_time": 0.123,
  "approach": "epoch_days",
  "implementation": "int",
  "error": "Error message (only if status is 'error')"
}
```

**Status values:**
- `sat` - Constraints are satisfiable; solution provided in `dates`, `ints`, `bools`
- `unsat` - Constraints are unsatisfiable; no solution exists
- `timeout` - Solver timed out before finding a solution
- `error` - An error occurred (e.g., syntax error); see `error` field for details

### Example Tool Call

An AI agent would call the tool with:

```json
{
  "declarations": ["x: Date", "y: Date"],
  "constraints": [
    "x >= Date(2024, 1, 1)",
    "y == x + Period(1, 0, 0)",
    "x.month == 6"
  ]
}
```

And receive:

```json
{
  "status": "sat",
  "dates": {
    "x": "Date(2024, 6, 1)",
    "y": "Date(2025, 6, 1)"
  },
  "execution_time": 0.015,
  "approach": "epoch_days",
  "implementation": "int"
}
```

### Dependencies

The MCP server requires additional dependencies:

```bash
pip install mcp uvicorn
```

These are included in `requirements.txt`.

## Constraint Language

### Date and Period Constructors

- `Date(year, month, day)` - Create a date literal
- `Period(years, months, days)` - Create a period literal

### Date Arithmetic

- `date + period` - Add period to date
- `date - period` - Subtract period from date
- `period + period` - Add periods
- `period - period` - Subtract periods
- `int * period` - Multiply period by concrete integer

### Date Comparisons

- `date == date`
- `date != date`
- `date < date`
- `date <= date`
- `date > date`
- `date >= date`

### Date Component Access

- `date.year` - Get year component
- `date.month` - Get month component
- `date.day` - Get day component

### Integer and Boolean Operations

- Integer comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Integer arithmetic: `+`, `-`, `*`, `/`, `%`
- Boolean operators: `&&` (AND), `||` (OR), `!` (NOT)
- Implications: `(condition) -> (consequence)`

### Variable Types

- `var: date` - Date variable
- `var: int` - Integer variable
- `var: bool` - Boolean variable

## Result Format

Both Python API and CLI return results with the following structure:

```python
{
    "status": "sat" or "unsat" or "timeout",
    "dates": {"x": Date(2000, 1, 1), ...},  # If sat
    "ints": {"n": 5, ...},                   # If sat
    "bools": {"flag": True, ...},           # If sat
    "execution_time": 0.123,                # Time in seconds
    "approach": "epoch_days",
    "implementation": "int"
}
```

**Status values:**
- `sat` - Constraints are satisfiable; solution fields are populated
- `unsat` - Constraints are unsatisfiable; no solution exists
- `timeout` - Solver timed out before determining satisfiability

## Advanced Usage

### Using the DateSATBuilder Directly

For more control, you can use the `DateSATBuilder` class directly:

```python
from datesat import DateSATBuilder, Date, Period

builder = DateSATBuilder(approach="epoch_days", implementation="int")

# Create variables
x = builder.add_date_var("x")
y = builder.add_date_var("y")
n = builder.add_int_var("n")

# Add constraints
builder.add_constraint(x >= Date(2000, 1, 1))
builder.add_constraint(y == x + Period(0, 1, 0))
builder.add_constraint(n > 5)
builder.add_constraint(n < 10)

# Solve
result = builder.solve()
```

### Export to SMT-LIB Format

```python
from datesat import DateSATBuilder, Date

builder = DateSATBuilder()
x = builder.add_date_var("x")
builder.add_constraint(x >= Date(2000, 1, 1))

# Get SMT-LIB format
smt2_string = builder.to_smt2()
print(smt2_string)

# Or enable automatic printing on solve
builder.enable_smtlib_print(True)
result = builder.solve()  # Will print SMT-LIB
```

## Solver Approaches

DateSAT provides several solvers with different performance characteristics.
Each approach is available in both **int** (integer arithmetic) and **bitvector** (bit-vector arithmetic) implementations.

In general, simple is often the slowest, and alpha beta table and epoch are relatively faster.
Please learn more by reading the paper.
