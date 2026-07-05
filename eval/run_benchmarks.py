import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path so `import datesat` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import datesat
from eval.utils.validation import check_results_dir

TIMEOUT_MS = 60000


def _get_smtlib_for_constraint(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int,
    use_maxsat: bool = False,
    bound: str = None,
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
            bound=bound,
        )

    exec_globals = {
        "Date": Date,
        "Period": Period,
        "DateSATBuilder": create_builder,
    }

    exec(constraint_code, exec_globals)
    builder = exec_globals.get("result") or exec_globals.get("builder")

    return builder.to_smt2() if builder else None


def run_constraint_check_only(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int = TIMEOUT_MS,
    bound: str = None,
) -> dict:
    """
    Solve-time evaluation runner: build the constraints, then time ONLY the
    solver's check() call and record the sat/unsat/timeout status. No model
    (solution) is ever extracted, so the reported execution_time is a clean
    solve-time measurement uncontaminated by model extraction or validation.
    """
    import time

    from z3 import BoolVal, sat, unsat

    from datesat.api import DateSATBuilder
    from datesat.constraint_parser import ConstraintParser
    from datesat.core import Date, Period

    constraint_id = constraint_data.get("id", "unknown")

    result = {
        "id": constraint_id,
        "constraints": constraint_data.get("constraints", []),
        "declarations": constraint_data.get("declarations", []),
        "approach": approach,
        "implementation": implementation,
        "bound": bound,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
    }

    try:
        parser = ConstraintParser()
        constraint_code = parser.parse_constraint_data(constraint_data)

        def create_builder():
            return DateSATBuilder(
                approach=approach,
                implementation=implementation,
                timeout_ms=timeout_ms,
                bound=bound,
            )

        exec_globals = {
            "DateSATBuilder": create_builder,
            "Date": Date,
            "Period": Period,
        }

        # Mirror datesat.solve's bounded semantics: in "paper" mode an
        # out-of-window concrete intermediate raises during constraint
        # building and is converted to an UNSAT constraint.
        try:
            exec(constraint_code, exec_globals)
        except ValueError as e:
            if "Date outside allowed range" in str(e):
                builder = exec_globals.get("builder")
                if builder is None:
                    raise
                builder.add_constraint(BoolVal(False))
            else:
                raise

        builder = exec_globals.get("builder")
        if builder is None:
            raise RuntimeError("Failed to create constraint solver")

        start = time.perf_counter()
        check_result = builder.solver.check()
        result["execution_time"] = time.perf_counter() - start

        if check_result == sat:
            result["status"] = "sat"
        elif check_result == unsat:
            result["status"] = "unsat"
        else:
            result["status"] = "timeout"

        print(f"  {constraint_id}: {result['status']} ({result['execution_time']:.3f}s)")

    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)
        print(f"  {constraint_id}: error ({e})")

    return result


def run_constraint_with_approach(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
    bound: str = None,
) -> dict:
    """
    Run a single constraint with a specific solver approach and implementation.

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
        "bound": bound,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
    }

    try:
        # Solve using the high-level API
        solve_result = datesat.solve(
            constraints=constraint_data,
            approach=approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            verbose=False,  # Suppress verbose output during benchmarking
            use_maxsat=use_maxsat,
            bound=bound,
        )

        # Extract status and execution time
        result["status"] = solve_result.get("status", "error")
        result["execution_time"] = solve_result.get("execution_time", 0.0)

        # Merge solution from all variable types
        merged_solution = {}
        for var_type in ["dates", "ints", "bools"]:
            vars_dict = solve_result.get(var_type, {})
            if vars_dict:
                for name, value in vars_dict.items():
                    merged_solution[name] = str(value) if var_type == "dates" else value

        result["solution"] = merged_solution or None

        # Generate SMT-LIB for benchmarking purposes (optional)
        try:
            result["smtlib"] = _get_smtlib_for_constraint(
                constraint_data, approach, implementation, timeout_ms, use_maxsat, bound
            )
        except Exception as e:
            result["smtlib_error"] = str(e)

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

    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)
        result["execution_time"] = 0.0
        print(f"❌ Error: {e}")

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


def write_timing_summary(all_results: dict, output_dir_path: Path, bound: str) -> dict:
    """
    Cross-encoding timing summary for one constraint set under one bound
    setting. Times use the penalized (PAR-1) convention - every entry's
    recorded execution_time counts, with timeouts contributing the timeout
    ceiling - matching checked_summary / compute_time.py. Solved-only times
    are included separately, clearly labeled.
    """
    import statistics

    summary = {"bound": bound, "approaches": {}}
    for approach_key, results in sorted(all_results.items()):
        total = len(results)
        by_status = {}
        for r in results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        solved = by_status.get("sat", 0) + by_status.get("unsat", 0)
        times_all = [r["execution_time"] for r in results if r.get("execution_time")]
        times_solved = [
            r["execution_time"]
            for r in results
            if r["status"] in ("sat", "unsat") and r.get("execution_time")
        ]
        summary["approaches"][approach_key] = {
            "total": total,
            "status_counts": by_status,
            "solve_rate_pct": (solved / total * 100) if total else 0.0,
            "mean_time_s": statistics.mean(times_all) if times_all else None,
            "median_time_s": statistics.median(times_all) if times_all else None,
            "std_dev_s": statistics.stdev(times_all) if len(times_all) > 1 else 0.0,
            "mean_time_solved_only_s": (
                statistics.mean(times_solved) if times_solved else None
            ),
            "median_time_solved_only_s": (
                statistics.median(times_solved) if times_solved else None
            ),
        }

    summary_path = output_dir_path / "timing_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    fmt = lambda v: f"{v:9.3f}" if v is not None else "        -"
    print(f"\nTiming summary (bound={bound}, penalized: timeouts count at their recorded time):")
    print(f"  {'approach':<24} {'solve%':>7} {'mean(s)':>9} {'median(s)':>9} {'std(s)':>9}")
    for approach_key, m in summary["approaches"].items():
        print(
            f"  {approach_key:<24} {m['solve_rate_pct']:>6.2f}% "
            f"{fmt(m['mean_time_s'])} {fmt(m['median_time_s'])} {fmt(m['std_dev_s'])}"
        )
    print(f"  Saved to: {summary_path}")

    return summary


def write_agreement_report(all_results: dict, output_dir_path: Path) -> dict:
    """
    Compare sat/unsat statuses across all encodings that ran on this
    constraint set (within a single bound setting) and write
    agreement_report.json. A disagreement is a constraint where at least one
    encoding reports sat and another reports unsat (timeouts/errors are
    undecided and never count as disagreements).
    """
    statuses_by_id: dict[str, dict[str, str]] = {}
    for approach_key, results in all_results.items():
        for r in results:
            statuses_by_id.setdefault(r["id"], {})[approach_key] = r["status"]

    disagreements = []
    fully_decided_agreements = 0
    for cid, statuses in sorted(statuses_by_id.items()):
        decided = {k: s for k, s in statuses.items() if s in ("sat", "unsat")}
        if len(set(decided.values())) > 1:
            disagreements.append({"id": cid, "statuses": statuses})
        elif len(decided) == len(statuses) and decided:
            fully_decided_agreements += 1

    report = {
        "approaches": sorted(all_results.keys()),
        "constraints": len(statuses_by_id),
        "fully_decided_and_agreeing": fully_decided_agreements,
        "num_disagreements": len(disagreements),
        "disagreements": disagreements,
        "statuses_by_constraint": statuses_by_id,
    }

    report_path = output_dir_path / "agreement_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"\nAgreement report: {report_path}")
    print(f"  Constraints: {report['constraints']}")
    print(f"  Fully decided & agreeing: {fully_decided_agreements}")
    if disagreements:
        print(f"  ⚠️  SAT/UNSAT DISAGREEMENTS: {len(disagreements)}")
        for d in disagreements[:10]:
            print(f"    - {d['id']}: {d['statuses']}")
        if len(disagreements) > 10:
            print(f"    ... and {len(disagreements) - 10} more")
    else:
        print("  ✅ No sat/unsat disagreements among encodings")

    return report


def run_constraints_file(
    constraints_file: str,
    output_dir: str,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
    approaches: list[str] = None,
    mode: str = "eval",
    bound: str = None,
):
    """Run benchmarks on constraints from a file with specified solver approaches.


    Args:
        constraints_file: Path to constraints file (JSON or JSONL)
        output_dir: Output directory for results
        timeout_ms: Timeout in milliseconds
        use_maxsat: Whether to use MaxSAT optimization
        approaches: List of approaches to test (None = all approaches)
        mode: "eval" (check-only: sat/unsat status + solve time, no model
              extraction) or "differential" (extract solutions for later
              validation against datetime)
        bound: Date bound mode - 'paper', 'datetime', or 'none'
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

    # Define all solver approaches per implementation.
    # The int implementation splits hybrid into hybrid_ymd / hybrid_epoch;
    # the bitvector implementation keeps the single "hybrid" approach.
    all_symbolic_approaches_by_impl = {
        "int": [
            "simple",
            "epoch_days",
            "hybrid_ymd",
            "hybrid_epoch",
            "hybrid_both",
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

    implementations = ["int"]  # Can add "bitvector" if needed

    # Build the set of (approach, implementation) pairs to run, honoring an
    # optional approach filter from the caller.
    runs = []
    for implementation in implementations:
        valid = all_symbolic_approaches_by_impl[implementation]
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
        for constraint in constraints:
            if mode == "eval":
                # Check-only: status + solve time, no model extraction. The
                # SMT-LIB dump uses a separate builder AFTER the timed check,
                # so it cannot contaminate the timing.
                result = run_constraint_check_only(
                    constraint, approach, implementation, timeout_ms, bound
                )
                try:
                    result["smtlib"] = _get_smtlib_for_constraint(
                        constraint, approach, implementation, timeout_ms, False, bound
                    )
                except Exception as e:
                    result["smtlib_error"] = str(e)
            else:
                result = run_constraint_with_approach(
                    constraint, approach, implementation, timeout_ms, use_maxsat, bound
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

    # Cross-encoding timing summary and sat/unsat agreement within this
    # bound setting
    write_timing_summary(all_results, output_dir_path, bound)
    if len(all_results) > 1:
        write_agreement_report(all_results, output_dir_path)

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
        "--mode",
        choices=["eval", "differential"],
        default="eval",
        help=(
            "eval: solve-time evaluation - only get sat/unsat and log the "
            "solve time (no model extraction), then compare whether sat/unsat "
            "agrees among all encodings. "
            "differential: differential testing - extract solutions, validate "
            "each SAT solution by executing the constraints concretely with "
            "Python datetime, and compare UNSAT across all encodings "
            "(an UNSAT is wrong only if another encoding has a validated SAT). "
            "Default: eval"
        ),
    )
    parser.add_argument(
        "--bound",
        choices=["paper", "datetime", "none", "all"],
        default="datetime",
        help=(
            "Date bound mode for the ablation study: "
            "paper = [1900-03-01..2100-02-28] (original bounded evaluation, "
            "including UNSAT-on-out-of-window intermediates); "
            "datetime = [0001-01-01..9999-12-31] (current default); "
            "none = no range bound at all (calendar well-formedness only); "
            "all = run paper, datetime, and none sequentially, each writing "
            "to its own results folder. "
            "Comparisons are only meaningful among encodings under the SAME "
            "bound setting. Default: datetime"
        ),
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
        "Each run is saved to results/run_1/, run_2/, … subdirectories.",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Optional label appended to the results folder name "
        "(e.g. --tag bench-paper -> <timestamp>_<bound>_<mode>_bench-paper). "
        "Useful to distinguish runs on derived datasets such as the "
        "bound-injected datesatbench_bounded variants.",
    )

    args = parser.parse_args()

    if args.maxsat and args.mode == "eval":
        parser.error(
            "--maxsat requires --mode differential (eval mode times a bare "
            "check() and never applies MaxSAT soft constraints)"
        )

    # Each invocation gets a fresh output root per bound setting to avoid
    # collisions and to make it easy to compare runs over time. The bound and
    # mode are part of the folder name so ablation runs are self-describing.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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

    datesatbench_root = _resolve_datesatbench_root(
        args.datesatbench_repo or os.environ.get("DATESATBENCH_REPO")
    )

    # Where to load constraints from (either local symlinks under eval/, or external repo)
    constraint_sets = [
        {
            "name": "LLM Generated Constraints",
            "constraints_file": datesatbench_root
            / "llm_constraints"
            / "constraints"
            / "constraints.json",
            # Always written under eval/results/<timestamp>_<bound>_<mode>/<subdir>
            "subdir": "llm",
        },
        {
            "name": "Grammar Constraints",
            "constraints_file": datesatbench_root
            / "grammar_constraints"
            / "constraints"
            / "constraints.json",
            "subdir": "grammar",
        },
        {
            "name": "Legal Document Constraints",
            "constraints_file": datesatbench_root
            / "legal_doc_constraints"
            / "constraints"
            / "constraints.jsonl",
            "subdir": "legal",
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
    print(f"  Mode: {args.mode}")
    print(f"  Bound: {args.bound}")
    print(f"  Timeout: {args.timeout}ms")
    print(f"  Runs: {args.runs}")
    print(f"  MaxSAT: {'Enabled' if args.maxsat else 'Disabled'}")
    if args.approaches:
        print(f"  Approaches: {args.approaches}")
    if args.datesatbenchs:
        print(f"  DateSATBench Datasets: {args.datesatbenchs}")
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

    def run_ablation_for_bound(bound: str) -> None:
        """Run the full benchmark (and analysis) for one bound setting."""
        folder = f"{timestamp}_{bound}_{args.mode}"
        if args.tag:
            folder += f"_{args.tag}"
        results_root = SCRIPT_DIR / "results" / folder

        # Collect (run_idx, dataset_name, output_dir) for deferred analysis
        completed_runs: list[tuple[int, str, Path]] = []

        # Run benchmarks for each constraint set, repeated args.runs times
        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n{'#'*70}")
                print(f"RUN {run_idx} of {args.runs}")
                print(f"{'#'*70}\n")

            for constraint_set in constraint_sets:
                name = constraint_set["name"]
                constraints_file = constraint_set["constraints_file"]
                base_output_dir = results_root / constraint_set["subdir"]

                # When running multiple times, nest results under run_N subdirectory
                output_dir = base_output_dir / f"run_{run_idx}" if args.runs > 1 else base_output_dir

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
                    mode=args.mode,
                    bound=bound,
                )

                completed_runs.append((run_idx, name, Path(output_dir)))
                print()  # Blank line between constraint sets

        # Record the run configuration alongside the results
        if completed_runs:
            results_root.mkdir(parents=True, exist_ok=True)
            (results_root / "run_config.json").write_text(
                json.dumps(
                    {
                        "mode": args.mode,
                        "bound": bound,
                        "timeout_ms": args.timeout,
                        "runs": args.runs,
                        "approaches": args.approaches,
                        "maxsat": args.maxsat,
                        "timestamp": timestamp,
                        "tag": args.tag,
                        "datesatbench_root": str(datesatbench_root),
                    },
                    indent=2,
                )
            )

        # Differential analysis: validate SAT solutions by executing constraints
        # concretely with Python datetime, and judge UNSATs against validated SATs
        # across encodings (within this bound setting).
        if args.mode == "differential" and completed_runs:
            print(f"\n{'#'*70}")
            print("RUNNING DIFFERENTIAL ANALYSIS FOR ALL RUNS")
            print(f"{'#'*70}")

            for run_idx, name, results_dir in completed_runs:
                run_label = f" (run {run_idx})" if args.runs > 1 else ""
                print(f"\n{'='*60}")
                print(f"Analyzing: {name}{run_label}")
                print(f"{'='*60}")

                if not results_dir.exists() or not results_dir.is_dir():
                    print(f"❌ Error: Results directory not found: {results_dir}")
                    continue

                summary_supported = check_results_dir(
                    results_dir, enumeration_filter="supported"
                )

                analysis_output = results_dir / "differential_report.json"
                analysis_output.write_text(
                    json.dumps(summary_supported, indent=2, sort_keys=False)
                )

                print(
                    f"\n✅ Differentially tested {summary_supported['constraints_checked']} constraints"
                )
                print(f"Differential report saved to: {analysis_output}")

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

    # --bound all runs the full ablation: each bound setting in sequence,
    # each writing to its own <timestamp>_<bound>_<mode> results folder.
    bounds_to_run = (
        ["paper", "datetime", "none"] if args.bound == "all" else [args.bound]
    )

    for i, bound in enumerate(bounds_to_run, 1):
        if len(bounds_to_run) > 1:
            print(f"\n{'@'*70}")
            print(f"@ BOUND SETTING {i}/{len(bounds_to_run)}: {bound.upper()}")
            print(f"{'@'*70}\n")
        run_ablation_for_bound(bound)


if __name__ == "__main__":
    main()
