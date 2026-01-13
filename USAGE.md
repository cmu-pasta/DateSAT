# DateSMT Usage Guide

DateSMT provides both a Python API and command-line interface for solving date constraints.

## Python API

### Basic Usage

```python
import datesmt

# Simple constraint solving
result = datesmt.solve(
    constraints=["x >= Date(2000,1,1)", "x < Date(2000,12,31)"],
    declarations=["x: date"]
)

if result["status"] == "sat":
    print(f"Solution found: {result['dates']['x']}")
```

### JSON Format

```python
import datesmt

# Using JSON format (same as CLI input)
result = datesmt.solve({
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
import datesmt

result = datesmt.solve({
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
import datesmt

# Use different solver approaches and implementations
result = datesmt.solve(
    constraints={...},
    approach="hybrid",           # naive, epoch_days, hybrid, alpha_beta, alpha_beta_table
    implementation="bitvector",  # int or bitvector
    timeout_ms=600000,          # 10 minutes
    verbose=True                # Print solver output
)
```

### Load from JSON File

```python
import datesmt
import json

with open('constraints.json') as f:
    constraint_data = json.load(f)

result = datesmt.solve(constraint_data)
```

## Command-Line Interface

### Basic Usage

```bash
# Read from stdin
./bin/datesmt.py < constraints.json

# Or using cat
cat constraints.json | python bin/datesmt.py

# Read from file
python bin/datesmt.py --file constraints.json
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
python bin/datesmt.py --approach hybrid --implementation bitvector < constraints.json

# Get JSON output instead of human-readable format
python bin/datesmt.py --output json < constraints.json

# Set timeout (in milliseconds)
python bin/datesmt.py --timeout 300000 < constraints.json  # 5 minutes

# Quiet mode (suppress solver output)
python bin/datesmt.py --quiet < constraints.json

# Show help
python bin/datesmt.py --help
```

### CLI Examples

```bash
# Simple constraint
echo '{"declarations":["x: date"],"constraints":["x >= Date(2000,1,1)"]}' | python bin/datesmt.py --quiet

# With file input and JSON output
python bin/datesmt.py --file constraints.json --output json

# Using hybrid approach with bitvector implementation
python bin/datesmt.py --approach hybrid --implementation bitvector --file constraints.json
```

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

Both API and CLI return results with the following structure:

```python
{
    "status": "sat" or "unsat",
    "dates": {"x": Date(2000, 1, 1), ...},  # If sat
    "ints": {"n": 5, ...},                   # If sat
    "bools": {"flag": True, ...},           # If sat
    "execution_time": 0.123,                # Time in seconds
    "approach": "epoch_days",
    "implementation": "int"
}
```

## Advanced Usage

### Using the DateSMTBuilder Directly

For more control, you can use the `DateSMTBuilder` class directly:

```python
from datesmt import DateSMTBuilder, Date, Period

builder = DateSMTBuilder(approach="epoch_days", implementation="int")

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
from datesmt import DateSMTBuilder, Date

builder = DateSMTBuilder()
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

DateSMT provides several solver approaches with different performance characteristics:

- **naive**: Direct encoding of date arithmetic (simple but slower)
- **epoch_days**: Convert dates to days since epoch (recommended, fast)
- **hybrid**: Hybrid approach combining multiple encodings
- **alpha_beta**: Alpha-beta encoding for optimized date arithmetic
- **alpha_beta_table**: Table-based alpha-beta encoding

Each approach is available in both **int** (integer arithmetic) and **bitvector** (bit-vector arithmetic) implementations.

For most use cases, the default `epoch_days` approach with `int` implementation provides the best performance.
