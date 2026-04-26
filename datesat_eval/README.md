# DateSAT evaluation (DateSATBench)

**Note:** Commands below assume you run them from the **DateSAT repo root**.

`datesat_eval/` contains the **evaluation + plotting utilities** for running DateSAT on the **DateSATBench** datasets.

**DateSATBench datasets live in a separate repo** (not vendored inside this repo).

## Prereqs (external DateSATBench repo)

1. **Clone** the DateSATBench repo somewhere (example path used below):

```bash
export DATESATBENCH_REPO="$HOME/Documents/GitHub/DateSATBench"
```

2. The evaluation script can read constraints directly from the external repo by passing `--datesatbench-repo` (recommended; no symlinks needed).

## Run the evaluation

Run all datasets (and run analysis at the end):

```bash
python3 datesat_eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO"
```

Run only one dataset (short names: `llm`, `grammar`, `legal`):

```bash
python3 datesat_eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO" --datesatbenchs llm
```

Add approach filtering / timeout, etc.:

```bash
python3 datesat_eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO" \
  --timeout 60000 \
  --approaches alpha_beta_table \
  --datesatbenchs legal
```

### Output location

Each invocation writes results under a timestamped directory in `datesat_eval/results/`:


## Utils

The `datesat_eval/utils/` directory contains utility scripts for analysis and plotting:

- **`plot_benchmark_stats.py`**: plots dataset stats (vars/constraints).
- **`plot_normalized_speedup.py`**: plots results from `run_benchmarks.py` outputs (run evaluation first).
- **`compute_time.py`**: execution time statistics from result JSON files.
- **`validation.py`**: validates solver solutions against constraints using concrete execution.