import argparse
import json
import multiprocessing as mp
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path so `import datesat` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import datesat
from eval.utils.validation import check_results_dir

TIMEOUT_MS = 60000
# Default wall-clock limit per instance, as a multiple of the solver timeout.
HARD_TIMEOUT_FACTOR = 2


def _get_smtlib_for_constraint(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int,
    use_maxsat: bool = False,
) -> str | None:
    """
    Generate SMT-LIB representation for a constraint.

    This is used for benchmarking purposes to save SMT-LIB files
    that can be replayed with other SMT solvers.
    """
    from datesat.api import DateSATBuilder
    from datesat.constraint_parser import ConstraintParser
    from datesat.core import Date, Period

    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)

    def create_builder():
        return DateSATBuilder(
            approach=approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            use_maxsat=use_maxsat,
        )

    exec_globals = {
        "Date": Date,
        "Period": Period,
        "DateSATBuilder": create_builder,
    }

    exec(constraint_code, exec_globals)
    builder = exec_globals.get("result") or exec_globals.get("builder")

    return builder.to_smt2() if builder else None


def _solve_task(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int,
    use_maxsat: bool,
) -> dict:
    """Solve one instance and keep only the result fields the runner records."""
    solve_result = datesat.solve(
        constraints=constraint_data,
        approach=approach,
        implementation=implementation,
        timeout_ms=timeout_ms,
        verbose=False,  # Suppress verbose output during benchmarking
        use_maxsat=use_maxsat,
    )

    # Merge solution from all variable types
    merged_solution = {}
    for var_type in ["dates", "ints", "bools"]:
        vars_dict = solve_result.get(var_type, {})
        if vars_dict:
            for name, value in vars_dict.items():
                merged_solution[name] = str(value) if var_type == "dates" else value

    return {
        "status": solve_result.get("status", "error"),
        "execution_time": solve_result.get("execution_time", 0.0),
        "solution": merged_solution or None,
    }


def _benchmark_worker(conn) -> None:
    """
    Child-process loop: for each task, send the solve result, then the SMT-LIB.

    The two are sent separately so the parent keeps the solve result even when
    SMT-LIB generation, which rebuilds the constraints, is the step that hangs.
    """
    while True:
        task = conn.recv()
        try:
            conn.send(("solved", _solve_task(*task)))
        except Exception as e:
            conn.send(("error", str(e)))
            continue
        try:
            conn.send(("smtlib", _get_smtlib_for_constraint(*task)))
        except Exception as e:
            conn.send(("smtlib_error", str(e)))


class _SolverWorker:
    """
    A child process that runs benchmark instances one at a time.

    datesat's timeout_ms only bounds the Z3 check. Building the constraints is
    unbounded and can hang (e.g. the simple approach unrolls one step per day of
    a Period, so a Period of 20,000 days never finishes asserting). Running in
    a child lets the parent enforce a wall-clock limit by killing it.
    """

    def __init__(self):
        self._ctx = mp.get_context("spawn")
        self._start()

    def __enter__(self) -> "_SolverWorker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _start(self) -> None:
        self._conn, child_conn = self._ctx.Pipe()
        self._proc = self._ctx.Process(
            target=_benchmark_worker, args=(child_conn,), daemon=True
        )
        self._proc.start()
        child_conn.close()

    def close(self) -> None:
        self._proc.kill()
        self._proc.join()
        self._conn.close()

    def send(self, task: tuple) -> None:
        self._conn.send(task)

    def recv(self, limit_s: float) -> tuple | None:
        """
        Next (kind, payload) message from the child, or None if none arrived
        within limit_s. If the child overran or died, it is replaced.
        """
        if self._conn.poll(limit_s):
            try:
                return self._conn.recv()
            except EOFError:
                self._proc.join()
                message = ("error", f"worker process died (exit code {self._proc.exitcode})")
        else:
            message = None
        self.close()
        self._start()
        return message


def run_constraint_with_approach(
    constraint_data: dict,
    approach: str,
    implementation: str,
    worker: _SolverWorker,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
    hard_timeout_ms: int | None = None,
) -> dict:
    """
    Run a single constraint with a specific solver approach and implementation.

    The work runs in `worker`. If solving, or separately SMT-LIB generation,
    exceeds hard_timeout_ms of wall-clock time (default: HARD_TIMEOUT_FACTOR x
    timeout_ms), the worker is killed and the step is abandoned; a killed
    solve is recorded as a timeout with "hard_timeout": True.

    Returns a dict containing the constraint ID, status, execution time,
    solution (if SAT), and optionally SMT-LIB representation.
    """
    constraint_id = constraint_data.get("id", "unknown")
    print(
        f"\n=== Running {constraint_id} ({approach.upper()}, {implementation.upper()}) ==="
    )
    print(f"Constraint: {constraint_data}")

    # Initialize result dictionary with default values
    result = {
        "id": constraint_id,
        "constraints": constraint_data.get("constraints", []),
        "declarations": constraint_data.get("declarations", []),
        "approach": approach,
        "implementation": implementation,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
        "hard_timeout": False,
    }

    limit_s = (hard_timeout_ms or HARD_TIMEOUT_FACTOR * timeout_ms) / 1000
    start_time = time.time()
    worker.send((constraint_data, approach, implementation, timeout_ms, use_maxsat))

    message = worker.recv(limit_s)
    if message is None:
        result["status"] = "timeout"
        result["hard_timeout"] = True
        result["execution_time"] = time.time() - start_time
        result["error_message"] = f"killed after exceeding the {limit_s:g}s hard timeout"
        print(f"⏱️ Killed after exceeding the {limit_s:g}s hard timeout")
        return result

    kind, payload = message
    if kind == "error":
        result["error_message"] = payload
        print(f"❌ Error: {payload}")
        return result
    result.update(payload)

    # SMT-LIB for benchmarking purposes (optional); it rebuilds the
    # constraints, so it gets its own hard timeout
    message = worker.recv(limit_s)
    if message is None:
        result["smtlib_error"] = f"exceeded the {limit_s:g}s hard timeout"
    elif message[0] == "smtlib":
        result["smtlib"] = message[1]
    else:
        result["smtlib_error"] = message[1]

    # Print status
    if result["status"] == "sat":
        print(f"✅ Solution found:")
        for name, value in result["solution"].items():
            print(f"  {name} = {value}")
    elif result["status"] == "timeout":
        print("⏱️ Solver timeout")
    elif result["status"] == "unsat":
        print("❌ No solution found (UNSAT)")
    else:
        print(f"❌ Status: {result['status']}")

    return result


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _load_constraints(constraints_file: str) -> list[dict]:
    """Load constraints from JSON or JSONL file."""
    constraints_file_path = Path(constraints_file)

    if constraints_file_path.suffix == ".jsonl":
        # JSONL format: one JSON object per line
        constraints = []
        with open(constraints_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                try:
                    constraint = json.loads(line)
                    constraints.append(constraint)
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: Skipping invalid JSON on line {line_num} of {constraints_file}: {e}"
                    )
    else:
        # JSON format: single JSON array/object
        with open(constraints_file, "r") as f:
            constraints = json.load(f)
            # If it's a single object, wrap it in a list
            if isinstance(constraints, dict):
                constraints = [constraints]

    return constraints


# Define all solver approaches per implementation.
# The int implementation splits hybrid into hybrid_ymd / hybrid_epoch;
# the bitvector implementation keeps the single "hybrid" approach.
ALL_SYMBOLIC_APPROACHES_BY_IMPL = {
    "int": [
        "simple",
        "epoch_days",
        "hybrid_ymd",
        "hybrid_epoch",
        "alpha_beta",
        # "alpha_beta_table",  # excluded from default run; pass via --approaches to include
    ],
    "bitvector": [
        "simple",
        "epoch_days",
        "hybrid",
        "alpha_beta",
        "alpha_beta_table",
    ],
}

IMPLEMENTATIONS = ["int"]  # Can add "bitvector" if needed


def _resolve_approach_pairs(approaches: list[str] | None) -> list[tuple[str, str]]:
    """Build the (approach, implementation) pairs to run, honoring an optional approach filter."""
    runs = []
    for implementation in IMPLEMENTATIONS:
        valid = ALL_SYMBOLIC_APPROACHES_BY_IMPL[implementation]
        if approaches is not None:
            selected = [a for a in approaches if a in valid]
            if not selected:
                print(
                    f"⚠️  Warning: No valid approaches for {implementation} in {approaches}. "
                    f"Using all approaches for {implementation}."
                )
                selected = valid
        else:
            selected = valid
        for approach in selected:
            runs.append((approach, implementation))
    return runs


def _next_run_index(dataset_dir: Path, result_files: list[str]) -> int:
    """
    Smallest N such that dataset_dir/run_N/ holds none of result_files.

    Re-invoking with the same approaches moves on to a fresh run_N, while
    invocations covering different approaches (e.g. launched in parallel)
    share one run_N.
    """
    n = 1
    while any((dataset_dir / f"run_{n}" / f).exists() for f in result_files):
        n += 1
    return n


def run_constraints_file(
    constraints_file: str,
    output_dir: str,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
    approaches: list[str] = None,
    hard_timeout_ms: int | None = None,
):
    """Run benchmarks on constraints from a file with specified solver approaches.


    Args:
        constraints_file: Path to constraints file (JSON or JSONL)
        output_dir: Output directory for results
        timeout_ms: Timeout in milliseconds
        use_maxsat: Whether to use MaxSAT optimization
        approaches: List of approaches to test (None = all approaches)
        hard_timeout_ms: Wall-clock limit per instance, after which it is
            killed (None = HARD_TIMEOUT_FACTOR x timeout_ms)
    """
    # Load constraints (supports both JSON and JSONL formats)
    constraints = _load_constraints(constraints_file)
    print(f"Loaded {len(constraints)} constraints from {constraints_file}")
    print(f"Output directory: {output_dir}")

    # Create output directories
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    smt_dir = output_dir_path / "smt_constraints"
    smt_dir.mkdir(parents=True, exist_ok=True)

    runs = _resolve_approach_pairs(approaches)

    if approaches is not None:
        print(f"Running with approach/implementation pairs: {runs}")

    all_results = {}

    # Run all (approach, implementation) pairs
    for approach, implementation in runs:
        print(f"\n{'='*60}")
        print(
            f"TESTING WITH {approach.upper()} APPROACH ({implementation.upper()})"
        )
        print(f"{'='*60}")

        results = []
        with _SolverWorker() as worker:
            for constraint in constraints:
                result = run_constraint_with_approach(
                    constraint,
                    approach,
                    implementation,
                    worker,
                    timeout_ms,
                    use_maxsat,
                    hard_timeout_ms,
                )

                # Save SMT-LIB representation to file if available
                if result.get("smtlib"):
                    constraint_id = _sanitize_filename(result.get("id", "unknown"))
                    smt_output_dir = smt_dir / approach / implementation
                    smt_output_dir.mkdir(parents=True, exist_ok=True)
                    smt_file_path = smt_output_dir / f"{constraint_id}.smt2"

                    try:
                        smt_file_path.write_text(result["smtlib"])
                        result["smtlib_file"] = str(smt_file_path)
                    except Exception as e:
                        result["smtlib_file_error"] = str(e)

                    # Remove smtlib from result to avoid bloating JSON files
                    del result["smtlib"]

                results.append(result)

        all_results[f"{approach}_{implementation}"] = results

        # Save results for this approach and implementation
        output_file = output_dir_path / f"{approach}_{implementation}.json"
        output_file.write_text(json.dumps(results, indent=2, default=str))
        print(f"\nResults saved to: {output_file}")

        # Print summary statistics
        total = len(results)
        successful = sum(1 for r in results if r["status"] == "sat")
        avg_time = (
            sum(r["execution_time"] for r in results) / total if total > 0 else 0.0
        )

        print(f"\nSummary for {approach} ({implementation}):")
        print(f"  Successful: {successful}/{total} ({successful/total*100:.1f}%)")
        print(f"  Avg time: {avg_time:.4f}s")

    return all_results



def main():
    """
    Run benchmarks on all constraint sets and optionally analyze results.

    Processes three constraint datesatbenchs:
    - Grammar Constraints
    - LLM Generated Constraints
    - Legal Document Constraints
    """
    SCRIPT_DIR = Path(__file__).parent

    parser = argparse.ArgumentParser(
        description="Test generated constraints with DateSAT and optionally analyze results"
    )
    parser.add_argument(
        "--datesatbench-repo",
        default=None,
        help=(
            "Path to an external DateSATBench repo checkout. If provided, constraint "
            "files are loaded from that repo (auto-detects either <repo>/datesatbench/... "
            "or <repo>/... layouts). Results are still written under eval/."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_MS,
        help="Timeout in milliseconds (default: 60000 = 60 seconds)",
    )
    parser.add_argument(
        "--hard-timeout",
        type=int,
        default=None,
        help="Wall-clock limit per instance in milliseconds, covering constraint "
        "construction as well as solving; an instance that exceeds it is killed and "
        f"recorded as a timeout (default: {HARD_TIMEOUT_FACTOR} x --timeout)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip analysis after constraint execution (default: run analysis)",
    )
    parser.add_argument(
        "--maxsat",
        action="store_true",
        help="Use MaxSAT optimization with soft constraints for dates near today",
    )
    parser.add_argument(
        "--approaches",
        nargs="+",
        default=None,
        help="List of approaches to test (e.g., --approaches alpha_beta_table alpha_beta_table_old). "
        "If not specified, all approaches are tested.",
    )
    parser.add_argument(
        "--datesatbenchs",
        nargs="+",
        default=None,
        help="List of datesatbench names to run (e.g., --datesatbenchs legal llm). "
        "Short names: 'legal', 'llm', 'grammar'. If not specified, all datesatbenchs are tested.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to repeat the full benchmark (default: 1). "
        "Each run is saved to a <dataset>/run_N/ subdirectory, numbered after any "
        "runs already present under the same --tag.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Name of the results subdirectory (default: a YYYYmmdd_HHMMSS timestamp). "
        "Invocations sharing a tag write into the same directory.",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Directory under which <tag>/ is created. Defaults to <DateSATBench repo>/results "
        "when --datesatbench-repo is given, otherwise eval/results.",
    )

    args = parser.parse_args()
    if args.hard_timeout is None:
        args.hard_timeout = HARD_TIMEOUT_FACTOR * args.timeout

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = args.tag or timestamp

    def _resolve_datesatbench_root(repo_path: str | None) -> Path:
        """
        Return the directory that contains llm_constraints/, grammar_constraints/, etc.

        Supports passing either:
        - the DateSATBench repo root (which contains a datesatbench/ package dir), or
        - the datesatbench/ directory itself.
        """
        if not repo_path:
            return SCRIPT_DIR
        p = Path(repo_path).expanduser().resolve()
        # If user passed the repo root, prefer the package directory.
        pkg_dir = p / "datesatbench"
        return pkg_dir if pkg_dir.exists() and pkg_dir.is_dir() else p

    def _find_repo_root(start: Path) -> Path | None:
        """Walk up from a dataset dir (e.g. datesatbench_new/) to the repo's pyproject.toml."""
        for d in [start, *start.parents]:
            if (d / "pyproject.toml").is_file():
                return d
        return None

    datesatbench_repo = args.datesatbench_repo or os.environ.get("DATESATBENCH_REPO")
    datesatbench_root = _resolve_datesatbench_root(datesatbench_repo)

    # Results go to <DateSATBench repo>/results/<tag>/ so they sit next to the
    # dataset they were produced from; eval/results/ is the fallback.
    if args.results_dir:
        results_base = Path(args.results_dir).expanduser().resolve()
    else:
        bench_repo_root = _find_repo_root(datesatbench_root) if datesatbench_repo else None
        results_base = (bench_repo_root or SCRIPT_DIR) / "results"
    results_root = results_base / tag

    # Where to load constraints from (either local symlinks under eval/, or external repo)
    constraint_sets = [
        {
            "name": "LLM Generated Constraints",
            "constraints_file": datesatbench_root
            / "llm_constraints"
            / "constraints"
            / "constraints.json",
            "output_dir": results_root / "llm",
        },
        {
            "name": "Grammar Constraints",
            "constraints_file": datesatbench_root
            / "grammar_constraints"
            / "constraints"
            / "constraints.json",
            "output_dir": results_root / "grammar",
        },
        {
            "name": "Legal Document Constraints",
            "constraints_file": datesatbench_root
            / "legal_doc_constraints"
            / "constraints"
            / "constraints.jsonl",
            "output_dir": results_root / "legal",
        },
    ]

    # Map short datesatbench names to full names
    datesatbench_name_map = {
        "legal": "Legal Document Constraints",
        "llm": "LLM Generated Constraints",
        "grammar": "Grammar Constraints",
    }

    # Convert short names to full names if needed
    if args.datesatbenchs:
        mapped_datesatbenchs = []
        for ds in args.datesatbenchs:
            if ds.lower() in datesatbench_name_map:
                mapped_datesatbenchs.append(datesatbench_name_map[ds.lower()])
            elif ds in datesatbench_name_map.values():
                # Already a full name
                mapped_datesatbenchs.append(ds)
            else:
                print(f"⚠️  Warning: Unknown datesatbench name: {ds}")
        args.datesatbenchs = mapped_datesatbenchs if mapped_datesatbenchs else None

    # Print configuration
    print(f"Configuration:")
    print(f"  Timeout: {args.timeout}ms")
    print(f"  Hard timeout: {args.hard_timeout}ms")
    print(f"  Runs: {args.runs}")
    print(f"  MaxSAT: {'Enabled' if args.maxsat else 'Disabled'}")
    print(f"  Analysis: {'Enabled' if not args.no_analysis else 'Disabled'}")
    if args.approaches:
        print(f"  Approaches: {args.approaches}")
    if args.datesatbenchs:
        print(f"  DateSATBench Datasets: {args.datesatbenchs}")
    print(f"  Results: {results_root}")
    print()

    # Filter constraint sets if specified
    if args.datesatbenchs:
        constraint_sets = [cs for cs in constraint_sets if cs["name"] in args.datesatbenchs]
        if not constraint_sets:
            print(f"⚠️  Warning: No matching datesatbenchs found. Available datesatbenchs:")
            print(f"    - legal (Legal Document Constraints)")
            print(f"    - llm (LLM Generated Constraints)")
            print(f"    - grammar (Grammar Constraints)")
            return

    # Record how this run was produced. Invocations sharing a --tag (e.g. one
    # per approach, run in parallel) accumulate their approaches and datasets.
    results_root.mkdir(parents=True, exist_ok=True)
    run_config_path = results_root / "run_config.json"
    prior = json.loads(run_config_path.read_text()) if run_config_path.exists() else {}
    approach_pairs = _resolve_approach_pairs(args.approaches)
    datasets = [
        cs["output_dir"].name for cs in constraint_sets if cs["constraints_file"].exists()
    ]
    run_config = {
        "timeout_ms": args.timeout,
        "hard_timeout_ms": args.hard_timeout,
        "approaches": sorted(
            set(prior.get("approaches", [])) | {a for a, _ in approach_pairs}
        ),
        "datasets": sorted(set(prior.get("datasets", [])) | set(datasets)),
        "maxsat": args.maxsat,
        "timestamp": prior.get("timestamp", timestamp),
        "tag": tag,
        "datesatbench_root": str(datesatbench_root),
    }
    run_config_path.write_text(json.dumps(run_config, indent=2))

    # Results always nest under <dataset>/run_N/. Numbering continues from
    # earlier invocations under the same tag, so repeated evals never overwrite.
    result_files = [f"{a}_{impl}.json" for a, impl in approach_pairs]
    first_run_index = {
        cs["name"]: _next_run_index(cs["output_dir"], result_files)
        for cs in constraint_sets
    }

    # Collect (run_idx, dataset_name, output_dir) for deferred analysis
    completed_runs: list[tuple[int, str, Path]] = []

    # Run benchmarks for each constraint set, repeated args.runs times
    for i in range(args.runs):
        if args.runs > 1:
            print(f"\n{'#'*70}")
            print(f"RUN {i + 1} of {args.runs}")
            print(f"{'#'*70}\n")

        for constraint_set in constraint_sets:
            name = constraint_set["name"]
            constraints_file = constraint_set["constraints_file"]
            run_idx = first_run_index[name] + i
            output_dir = constraint_set["output_dir"] / f"run_{run_idx}"

            print(f"{'='*70}")
            print(f"Running: {name}")
            print(f"{'='*70}")
            print(f"Constraints file: {constraints_file}")
            print(f"Output directory: {output_dir}")

            if not constraints_file.exists():
                print(f"⚠️  Skipping - Constraints file not found: {constraints_file}\n")
                continue

            output_dir.mkdir(parents=True, exist_ok=True)

            run_constraints_file(
                str(constraints_file),
                str(output_dir),
                args.timeout,
                use_maxsat=args.maxsat,
                approaches=args.approaches,
                hard_timeout_ms=args.hard_timeout,
            )

            completed_runs.append((run_idx, name, Path(output_dir)))
            print()  # Blank line between constraint sets

    # Run analysis for all completed runs at the end
    if not args.no_analysis and completed_runs:
        print(f"\n{'#'*70}")
        print("RUNNING ANALYSIS FOR ALL RUNS")
        print(f"{'#'*70}")

        for run_idx, name, results_dir in completed_runs:
            run_label = f" (run {run_idx})"
            print(f"\n{'='*60}")
            print(f"Analyzing: {name}{run_label}")
            print(f"{'='*60}")

            if not results_dir.exists() or not results_dir.is_dir():
                print(f"❌ Error: Results directory not found: {results_dir}")
                continue

            summary_supported = check_results_dir(
                results_dir, enumeration_filter="supported"
            )

            analysis_output = results_dir / "checked_summary_with_baseline.json"
            analysis_output.write_text(
                json.dumps(summary_supported, indent=2, sort_keys=False)
            )

            print(
                f"\n✅ Analyzed {summary_supported['constraints_checked']} constraints "
                "(enumeration supported)"
            )
            print(f"Analysis saved to: {analysis_output}")

            enum_support = summary_supported.get("enumeration_support", {})
            not_supported_count = enum_support.get("not_supported_count", 0)
            if not_supported_count > 0:
                unsupported_summary = check_results_dir(
                    results_dir, enumeration_filter="not_supported"
                )
                unsupported_output = (
                    results_dir / "checked_summary_without_baseline.json"
                )
                unsupported_output.write_text(
                    json.dumps(unsupported_summary, indent=2, sort_keys=False)
                )
                print(
                    f"⚠️ {not_supported_count} constraints without enumeration support "
                    f"(saved to: {unsupported_output})"
                )

            counts = summary_supported["counts_by_approach"]
            print(f"\nSummary by approach (enumeration supported):")
            for approach, counts_dict in counts.items():
                total = sum(counts_dict.values())
                correct = counts_dict.get("correct", 0)
                percentage = correct / total * 100 if total > 0 else 0
                print(f"  {approach}: {correct}/{total} correct ({percentage:.1f}%)")


if __name__ == "__main__":
    main()
