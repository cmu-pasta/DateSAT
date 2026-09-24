# DateSAT evaluation (DateSATBench)

**Note:** Commands below assume you run them from the **DateSAT repo root**.

`eval/` contains the **evaluation + plotting utilities** for running DateSAT on the **DateSATBench** datasets.

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
python3 eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO"
```

Run only one dataset (short names: `llm`, `grammar`, `legal`):

```bash
python3 eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO" --datesatbenchs llm
```

Add approach filtering / timeout, etc.:

```bash
python3 eval/run_benchmarks.py --datesatbench-repo "$DATESATBENCH_REPO" \
  --timeout 60000 \
  --approaches alpha_beta_table \
  --datesatbenchs legal
```

`--timeout` only bounds the Z3 check; building the constraints is not covered by it and can hang (e.g. `simple` on a `Period` with tens of thousands of days). Each instance therefore runs in a child process that is killed after `--hard-timeout` ms of wall-clock time (default: 60000). A killed instance is recorded as `"status": "timeout"` with `"hard_timeout": true`. Each result also splits `execution_time` into `build_time` (constructing the constraints) and `solve_time` (the Z3 check and model extraction).

### Output location

Results are written to `<results-dir>/<tag>/`:

- `<results-dir>` defaults to `<DateSATBench repo>/results` (the repo containing the dataset passed to `--datesatbench-repo`), or `eval/results/` if no DateSATBench repo is given. Override with `--results-dir`.
- `<tag>` defaults to a `YYYYmmdd_HHMMSS` timestamp. Override with `--tag`; invocations sharing a tag write into the same directory.
- Every run goes in its own `run_N/`. Each invocation takes, per dataset, the lowest `N` whose `run_N/` has no result file for the approaches being run. So re-running with the same `--tag` adds `run_2`, `run_3`, …, while invocations covering *different* approaches (e.g. one per approach, launched in parallel) share a `run_N`. `--runs K` produces `K` consecutive run directories.

```
<results-dir>/<tag>/
├── run_config.json                # timeout, approaches, datasets, dataset root
└── <llm|grammar|legal>/
    └── run_N/
        ├── <approach>_int.json    # per-constraint status, time, solution
        └── checked_summary_with_baseline.json   # unless --no-analysis
```

A result file is written only once its approach finishes every constraint, so a killed run leaves its `run_N/` reusable. Starting the *same* approach again while an earlier invocation is still running will pick the same `run_N`.


## Utils

The `eval/utils/` directory contains utility scripts for analysis and plotting:

- **`plot_benchmark_stats.py`**: plots dataset stats (vars/constraints).
- **`plot_normalized_speedup.py`**: plots results from `run_benchmarks.py` outputs (run evaluation first).
- **`compute_time.py`**: execution time statistics from result JSON files.
- **`validation.py`**: validates solver solutions against constraints using concrete execution.