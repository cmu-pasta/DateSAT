# DateSAT: A Framework for Solving Date and Period Constraints

[![CI Badge](https://github.com/cmu-pasta/DateSAT/actions/workflows/ci.yml/badge.svg)](https://github.com/cmu-pasta/DateSAT/actions/workflows/ci.yml)
[![Coverage Badge](https://pastalab.org/DateSAT/badge.svg)](https://pastalab.org/DateSAT/)

## Overview

DateSAT provides implementations to multiple encodings strategies for solving date and calendar period constraints. 
It encodes DateSAT constraints into Z3 integer constraints for efficient symbolic analysis.

The library offers both a high-level Python API and a command-line interface for solving date constraints with support for:
- Date and period arithmetic
- Date, Integer and Boolean variables
- Complex boolean expressions with `&&`, `||`, `!`, and implications (`->`)
- Date component access (`.year`, `.month`, `.day`)
- Multiple solver approaches optimized for different use cases

## What's Inside

| Path | What it holds |
|---|---|
| `datesat/` | The library. `solver.py` is the high-level entry point (`datesat.solve`), `api.py` the builder that dispatches to an encoding, `core.py` the concrete `Date` and `Period` types, and `constraint_parser.py` the parser for the constraint language. |
| `datesat/symbolic_int/` | The five encodings into Z3 integer arithmetic (paper §4): `simple_int.py`, `epoch_days_int.py`, `hybrid_init_ymd_int.py`, `hybrid_init_epoch_int.py`, and `alpha_beta_int.py`. |
| `datesat/router/` | The router (paper §6): static feature extraction and the bundled trained model (`model.json`) that picks an encoding per constraint. |
| `datesat/constraint_validator.py`, `datesat/verus_oracle.py` | Checks a solved assignment against the constraints, optionally using the executable Verus reference semantics from `proofs/`. |
| `bin/` | The command-line interface (`datesat_cli.py`) and the MCP server (`datesat_mcp.py`, `mcp_server.py`). |
| `tests/` | Unit tests for each encoding, property-based tests of the core date and period operations, and the checks of the reference semantics against `dateutil` and `java.time` (see `tests/README.md`). |
| `proofs/` | The Verus specification of the semantics and encodings, with the machine-checked equisatisfiability proofs and the executable oracle (see `proofs/README.md`). |
| `future_work/` | Bounded-domain variants not discussed in the paper: the bitvector encodings and the enumeration baseline. |
| `paper/sec2/` | Scripts that reproduce the motivating example of paper §2 (Figs. 1 and 4a). |
| `docs/` | Implementation notes on the encodings, and on the integer vs bitvector implementations. |
| `USAGE.md` | Full reference for the Python API, CLI, MCP server, and result format. |

## Paper

DateSAT is described in our paper: [arXiv](TODO-ARXIV-LINK).
This repository holds the solver and the mechanized proofs; the benchmark, the evaluation scripts and the raw results are in the [DateSATBench repository](https://github.com/cmu-pasta/DateSATBench).

| Repository | What it holds | Paper |
|---|---|---|
| This one, [`proofs/`](proofs/) | The Verus specification of the semantics and encodings, with the machine-checked proofs | §3, §4.5 |
| This one, everything else | The solver: every encoding, the router, and the test suites | §2, §4, §6, §7 |
| [DateSATBench](https://github.com/cmu-pasta/DateSATBench) | The benchmark and its generators, the evaluation and analysis scripts, and the raw results | §5, §6 |

### Mechanized proofs (§4.5; contribution 3)

| In the paper | In [`proofs/src/`](proofs/src/) |
|---|---|
| Semantics of dates and periods (Fig. 3, Defs. 3.1–3.4) | [`semantics.rs`](proofs/src/semantics.rs), [`period.rs`](proofs/src/period.rs) |
| Theorem 3.5 (normalization and well-formedness) | `theorem_date_add_period_preserves_validity`, in [`semantics.rs`](proofs/src/semantics.rs) |
| Property 3.6 (monotonicity) | `theorem_date_add_period_is_monotonic`, in [`monotonicity.rs`](proofs/src/monotonicity.rs) |
| Constraint language, evaluation, satisfiability (§3.2–3.3) | [`ast_eval.rs`](proofs/src/ast_eval.rs) |
| Theorem 4.2 (Simple) | `theorem_ast_simple_date_equisat`; encoding in [`simple_date.rs`](proofs/src/simple_date.rs) |
| Theorem 4.3 (Epoch-based) | `theorem_ast_epoch_delta_equisat`; encoding in [`epoch_delta.rs`](proofs/src/epoch_delta.rs) |
| Theorem 4.4 (Hybrid init_ymd) | `theorem_ast_hybrid_ymd_equisat`; encoding in [`hybrid_ymd.rs`](proofs/src/hybrid_ymd.rs) |
| Theorem 4.5 (Hybrid init_epoch) | `theorem_ast_hybrid_epoch_equisat`; encoding in [`hybrid_epoch.rs`](proofs/src/hybrid_epoch.rs) |
| Theorem 4.6 (Alpha-Beta) | `theorem_ast_ab_equisat`; encoding in [`alpha_beta.rs`](proofs/src/alpha_beta.rs) |
| Congruence and the proof sketch | [`equivalence.rs`](proofs/src/equivalence.rs) |

All seven statements are asserted together in [`main.rs`](proofs/src/main.rs). To check them, install [Verus](https://github.com/verus-lang/verus/blob/main/INSTALL.md), then:

```bash
cd proofs
/path/to/verus src/main.rs        # expected: 152 verified, 0 errors
```

The proofs use no axioms and no `assume` or `admit`.
Two things are not checked by the command above, and no theorem depends on either: the line-parsing driver of the executable test oracle (`#[verifier::external_body]` in `oracle.rs`), and two auxiliary lemmas about scaling periods in `period.rs` that are only compiled with `--cfg slow_proofs`.
See [`proofs/README.md`](proofs/README.md) for more.

### The solver (§4; contribution 4)

| In the paper | In this repository |
|---|---|
| Motivating example of §2 (Figs. 1 and 4a) | [`paper/sec2/`](paper/sec2/) |
| Constraint language (§3.2, Fig. 5) | [`datesat/constraint_parser.py`](datesat/constraint_parser.py); usage below and in [`USAGE.md`](USAGE.md) |
| Simple encoding (§4.1) | [`datesat/symbolic_int/simple_int.py`](datesat/symbolic_int/simple_int.py) |
| Epoch-based encoding (§4.2) | [`datesat/symbolic_int/epoch_days_int.py`](datesat/symbolic_int/epoch_days_int.py) |
| Hybrid encodings (§4.3) | [`datesat/symbolic_int/hybrid_init_ymd_int.py`](datesat/symbolic_int/hybrid_init_ymd_int.py), [`hybrid_init_epoch_int.py`](datesat/symbolic_int/hybrid_init_epoch_int.py); worked examples in [`docs/hybrid_examples.md`](docs/hybrid_examples.md) |
| Alpha-Beta encoding (§4.4) | [`datesat/symbolic_int/alpha_beta_int.py`](datesat/symbolic_int/alpha_beta_int.py) |
| Interface every encoding implements | [`docs/overview.md`](docs/overview.md) |
| Router, as the solver uses it (§6) | [`datesat/router/`](datesat/router/) |

### The benchmark (§5; contribution 5)

| In the paper | In [DateSATBench](https://github.com/cmu-pasta/DateSATBench) |
|---|---|
| The 800 constraints | `datesatbench/*/constraints/`: [`100 LLM-synthesized`](https://github.com/cmu-pasta/DateSATBench/tree/main/datesatbench/llm_constraints/constraints), [`500 grammar-sampled`](https://github.com/cmu-pasta/DateSATBench/tree/main/datesatbench/grammar_constraints/constraints), [`200 legally grounded`](https://github.com/cmu-pasta/DateSATBench/tree/main/datesatbench/legal_doc_constraints/constraints) |
| LLM prompt and feedback loop | [`datesatbench/llm_constraints/generator/constraint_generator.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/datesatbench/llm_constraints/generator/constraint_generator.py) (`SYSTEM_PROMPT`) |
| Fandango grammar and swarm-testing knobs | [`datesatbench/grammar_constraints/generator`](https://github.com/cmu-pasta/DateSATBench/tree/main/datesatbench/grammar_constraints/generator): `grammar.fan`, `flags.toml`, `flag.md` |
| Pipeline that extracts and translates IRC provisions | [`datesatbench/legal_doc_constraints/generator`](https://github.com/cmu-pasta/DateSATBench/tree/main/datesatbench/legal_doc_constraints/generator) (prompt: `LEGAL_EXTRACTION_PROMPT` in `llm_extractor.py`) |
| The 61 features | [`analysis/features/features.md`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/features/features.md); extractor in [`analysis/features/extract_features.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/features/extract_features.py); values in [`results/analysis/features.csv`](https://github.com/cmu-pasta/DateSATBench/blob/main/results/analysis/features.csv) |
| Fig. 6b (t-SNE projection) | [`results/analysis/plots/dataset_tsne.pdf`](https://github.com/cmu-pasta/DateSATBench/blob/main/results/analysis/plots/dataset_tsne.pdf), drawn by [`analysis/stats/plot_tsne.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/stats/plot_tsne.py) |

### The evaluation (§6)

| In the paper | In [DateSATBench](https://github.com/cmu-pasta/DateSATBench) |
|---|---|
| Raw results of the five encodings, 10 runs | [`results/runs/encodings`](https://github.com/cmu-pasta/DateSATBench/tree/main/results/runs/encodings) |
| Raw results of the router, 10 runs | [`results/runs/router`](https://github.com/cmu-pasta/DateSATBench/tree/main/results/runs/router) |
| Scripts that run the evaluation | [`analysis/run`](https://github.com/cmu-pasta/DateSATBench/tree/main/analysis/run) |
| Table 1 | [`results/analysis/outcomes_table.tex`](https://github.com/cmu-pasta/DateSATBench/blob/main/results/analysis/outcomes_table.tex) and `outcomes_table_cactus_*.pdf`, written by [`analysis/report/paper_table.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/report/paper_table.py) |
| Numbers quoted in the text of §6 | [`results/analysis/joined.csv`](https://github.com/cmu-pasta/DateSATBench/blob/main/results/analysis/joined.csv); `python -m analysis.stats.solver_outcomes --compare` prints the per-encoding outcomes, and `results/analysis/report.html` shows the rest |
| Router: training and cross-validation | [`analysis/router`](https://github.com/cmu-pasta/DateSATBench/tree/main/analysis/router); models and results in [`results/analysis/model`](https://github.com/cmu-pasta/DateSATBench/tree/main/results/analysis/model) and [`model_cross_validation`](https://github.com/cmu-pasta/DateSATBench/tree/main/results/analysis/model_cross_validation) |
| Fig. 7 | [`results/analysis/plots/router.pdf`](https://github.com/cmu-pasta/DateSATBench/blob/main/results/analysis/plots/router.pdf), drawn by [`analysis/router/plot_router.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/router/plot_router.py) |

### Testing and validation (§7)

| In the paper | Where |
|---|---|
| Semantics against Python's `dateutil` and Java's `java.time` | [`tests/semantics_vs_libraries/`](tests/semantics_vs_libraries/) |
| Unit tests of each encoding | [`tests/unit_tests/`](tests/unit_tests/) |
| Property-based tests of date and period operations | [`tests/property_tests/`](tests/property_tests/) |
| Validation of every model returned on DateSATBench | [`analysis/run/validation.py`](https://github.com/cmu-pasta/DateSATBench/blob/main/analysis/run/validation.py) in DateSATBench; outcome per run in `checked_summary_with_baseline.json` |

## Supported Ranges

By default, dates are **unbounded**: a `Date` is any calendar-valid day of the proleptic Gregorian calendar, so years may be zero, negative, or beyond 9999, and `Period` components are arbitrary integers. 
A bound is not required for decidability (see the paper, Section 3.3). 
Solutions are returned as `datesat.Date` objects; 
`Date.to_python_date()` converts one to a `datetime.date` and raises `ValueError` outside Python's range (years 1..9999).

Passing `python_bounds=True` to `datesat.solve` or `DateSATBuilder` (`--python-bounds` on the CLI, `python_bounds` on the MCP tool) restricts every date variable and every intermediate `Date + Period` result to Python's `datetime.date` range, years 1..9999, and handles every concrete `Date` (literals in the constraints and the dates of the model) through `datetime`. A concrete date outside the range raises `ValueError`, as `datetime` does.

## Quick Start

### Installation

```bash
# 1. Setup conda environment
conda create -y -n datesat python=3.10
conda activate datesat

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install DateSat itself, so it can be imported from any directory
pip install -e .
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
# This is the standard input format for DATESAT
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
    approach="alpha_beta",       # simple, epoch_days, hybrid_init_ymd, hybrid_init_epoch, alpha_beta, or router
    timeout_ms=600000,           # 10 minutes
    python_bounds=False          # True: bound every date to years 1..9999
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
python bin/datesat_cli.py --approach alpha_beta --output json < constraints.json
python bin/datesat_cli.py --python-bounds < constraints.json
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
