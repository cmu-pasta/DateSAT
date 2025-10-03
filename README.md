# DATE-SMT

[![coverage](https://github.com/angelc2/Date-SMT/actions/workflows/coverage.yml/badge.svg)](https://github.com/angelc2/Date-SMT/actions/workflows/coverage.yml)

Coverage site (main): https://angelc2.github.io/Date-SMT/main/

Per-branch coverage: https://angelc2.github.io/Date-SMT/<branch>/  (e.g., https://angelc2.github.io/Date-SMT/dev/)

A Python library for symbolic analysis of date-based computations using Z3.

## Overview

DATE-SMT provides both baseline and advanced implementations for expressing and solving date/time constraints using Z3. It converts DATE-SMT expressions into Z3 integer-only constraints for efficient symbolic analysis.

## Installation

```bash
# 1. Setup conda environment
conda create -y -n datesmt python=3.10
conda activate datesmt

# 2. Install dependencies
pip install -r requirements/core.txt
# Optionally install the dev dependencies and the llm constraints generation pipeline dependencies
pip install -r requirements/dev.txt
pip install -r requirements/llm_pipeline.txt

# 3. Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

## Core Components

### Date/Period Classes (`datesmt/core.py`)
- **Unified**: Single Date/Period class with year/month/day representation
- **Epoch Support**: Built-in epoch conversion methods for efficient constraint solving

### Symbolic Constraint Solving (`datesmt/`)
- **DateVar**: Symbolic date variables
- **PeriodVar**: Symbolic period variables
- **Z3 Integration**: Direct constraint translation to Z3

## CI/CD and Coverage

- **CI/CD**: Continuous Integration runs tests and coverage on each push/PR via GitHub Actions. Continuous Delivery publishes the HTML coverage site using GitHub Pages.
- **Coverage measurement**: We collect branch and line coverage for the `datesmt` package using `coverage.py` via `pytest-cov`.

### Run tests and build the coverage site locally

```bash
# from repo root
python tests/build_coverage_site.py
# output will be under documentation/coverage
open documentation/coverage/index.html  # macOS
```

The coverage site includes a top-level summary and a detailed HTML report (`documentation/coverage/coverage_html/index.html`).

### Ensure CI runs and Pages deploy on push

- Commit the `.github/workflows/coverage.yml` and `.github/workflows/gh-pages-coverage.yml` files.
- GitHub Pages is automatically published per-branch under `/[branch]/` on pushes.
