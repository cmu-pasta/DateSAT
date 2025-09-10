# Date-SMT
A lightweight Python prototype for expressing and solving date/time constraints using Z3. Constraints are internally encoded using Z3 integer arithmetic.

---

## Development

### Apple Silicon

```bash
# 1. Setup mamba/conda (mamba resolves dependencies faster than conda)
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh
bash Miniforge3-MacOSX-arm64.sh

# 2. Create a Python environment
mamba create -y -n datesmt python=3.10
conda activate datesmt

# 3. Install core dependencies
pip install -r requirements/core.txt

# 4. Setup dev dependencies (optional, for contributors)
pip install -r requirements/dev.txt

# 5. (Optional) Install Z3 from source if you're modifying solver internals
# git clone https://github.com/Z3Prover/z3.git
# cd z3 && python scripts/mk_make.py --python && cd build && make && sudo make install

# 6. Append project root to PYTHONPATH before running scripts
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

---

### Note: pre-commit

We use `pre-commit` to enforce consistent formatting and linting. After installing it, the checks will run automatically before each commit. If a violation is found, the tools will fix the files. You'll need to stage the changes again and retry the commit.

```bash
pre-commit install
```

---
