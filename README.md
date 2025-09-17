# DATE-SMT

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
