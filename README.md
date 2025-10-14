# DATE-SMT

[![CI Badge](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml/badge.svg)](https://github.com/cmu-pasta/Date-SMT/actions/workflows/ci.yml)
[![Coverage Badge](https://pastalab.org/Date-SMT/badge.svg)](https://pastalab.org/Date-SMT/)

A Python library for symbolic analysis of date-based computations using Z3.

## Overview

DATE-SMT provides both baseline and epoch_days implementations for expressing and solving date/time constraints using Z3. It converts DATE-SMT expressions into Z3 integer-only constraints for efficient symbolic analysis.

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

- **CI/CD**: On each push to `dev`, CI builds the coverage site and commits it to `docs/`, which GitHub Pages serves.
- **Coverage measurement**: We collect branch and line coverage for the `datesmt` package using `coverage.py` via `pytest-cov`.

### Run tests and build the coverage site locally

```bash
# from repo root
python tests/build_coverage_site.py
# output will be under documentation/coverage by default
# to match Pages layout locally, write directly into docs/
COVERAGE_SITE_DIR=docs python tests/build_coverage_site.py
open docs/index.html  # macOS
```

The coverage site root serves the detailed coverage report.

### Configure GitHub Pages (one-time)

- Repo → Settings → Pages
- Source: Deploy from a branch
- Branch: dev, Folder: /docs
