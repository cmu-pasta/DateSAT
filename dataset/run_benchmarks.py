import argparse
import json
import os
import re
import sys
from pathlib import Path

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import datesmt
from dataset.utils.validation import check_results_dir

TIMEOUT_MS = 60000


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
    from datesmt.api import DateSMTBuilder
    from datesmt.constraint_parser import ConstraintParser
    from datesmt.core import Date, Period

    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)

    def create_builder():
        return DateSMTBuilder(
            approach=approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            use_maxsat=use_maxsat,
        )

    exec_globals = {
        "Date": Date,
        "Period": Period,
        "DateSMTBuilder": create_builder,
    }

    exec(constraint_code, exec_globals)
    builder = exec_globals.get("result") or exec_globals.get("builder")

    return builder.to_smt2() if builder else None


def run_constraint_with_approach(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
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
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
    }

    try:
        # Solve using the high-level API
        solve_result = datesmt.solve(
            constraints=constraint_data,
            approach=approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            verbose=False,  # Suppress verbose output during benchmarking
            use_maxsat=use_maxsat,
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
                constraint_data, approach, implementation, timeout_ms, use_maxsat
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


def run_constraints_file(
    constraints_file: str,
    output_dir: str,
    timeout_ms: int = TIMEOUT_MS,
    use_maxsat: bool = False,
    approaches: list[str] = None,
):
    """Run benchmarks on constraints from a file with specified solver approaches.


    Args:
        constraints_file: Path to constraints file (JSON or JSONL)
        output_dir: Output directory for results
        timeout_ms: Timeout in milliseconds
        use_maxsat: Whether to use MaxSAT optimization
        approaches: List of approaches to test (None = all approaches)
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

    # Define all solver approaches and implementations to test
    all_symbolic_approaches = [
        "naive",
        # "epoch_days",
        # "hybrid",
        # "alpha_beta",
        # "alpha_beta_table"
        # "epoch_days",
        # "hybrid",
        # "alpha_beta",
        # "alpha_beta_table"
    ]


    # Filter approaches if specified
    if approaches is not None:
        symbolic_approaches = [a for a in approaches if a in all_symbolic_approaches]
        if not symbolic_approaches:
            print(
                f"⚠️  Warning: No valid approaches found in {approaches}. Using all approaches."
            )
            print(
                f"⚠️  Warning: No valid approaches found in {approaches}. Using all approaches."
            )
            symbolic_approaches = all_symbolic_approaches
        else:
            print(f"Running with approaches: {symbolic_approaches}")
    else:
        symbolic_approaches = all_symbolic_approaches


    implementations = ["int"]  # Can add "bitvector" if needed

    all_results = {}

    # Run all approaches with their respective implementations
    for approach in symbolic_approaches:
        for implementation in implementations:
            print(f"\n{'='*60}")
            print(
                f"TESTING WITH {approach.upper()} APPROACH ({implementation.upper()})"
            )
            print(f"{'='*60}")

            results = []
            for constraint in constraints:
                result = run_constraint_with_approach(
                    constraint, approach, implementation, timeout_ms, use_maxsat
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

    Processes three constraint datasets:
    - Grammar Constraints
    - LLM Generated Constraints
    - Legal Document Constraints
    """
    SCRIPT_DIR = Path(__file__).parent

    constraint_sets = [
        {
            "name": "Grammar Constraints",
        {
            "name": "Grammar Constraints",
            "constraints_file": SCRIPT_DIR
            / "grammar_constraints"
            / "constraints"
            / "constraints.json",
            "output_dir": SCRIPT_DIR / "grammar_constraints" / "results",
        },
        # {
        #     "name": "LLM Generated Constraints",
        #     "constraints_file": SCRIPT_DIR
        #     / "llm_constraints"
        #     / "constraints"
        #     / "constraints.json",
        #     "output_dir": SCRIPT_DIR / "llm_constraints" / "results",
        # },
        # {
        #     "name": "Legal Document Constraints",
        #     "constraints_file": SCRIPT_DIR
        #     / "legal_doc_constraints"
        #     / "constraints"
        #     / "constraints.jsonl",
        #     "output_dir": SCRIPT_DIR / "legal_doc_constraints" / "results",
        # },
    ]

    parser = argparse.ArgumentParser(
        description="Test generated constraints with DATE-SMT and optionally analyze results"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_MS,
        help="Timeout in milliseconds (default: 60000 = 60 seconds)",
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
        "If not specified, all approaches are tested.",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=None,
        help="List of dataset names to run (e.g., --datasets legal llm). "
        "Short names: 'legal', 'llm', 'grammar'. If not specified, all datasets are tested.",
        "Short names: 'legal', 'llm', 'grammar'. If not specified, all datasets are tested.",
    )

    args = parser.parse_args()

    # Map short dataset names to full names
    dataset_name_map = {
        "legal": "Legal Document Constraints",
        "llm": "LLM Generated Constraints",
        "grammar": "Grammar Constraints",
    }

    # Convert short names to full names if needed
    if args.datasets:
        mapped_datasets = []
        for ds in args.datasets:
            if ds.lower() in dataset_name_map:
                mapped_datasets.append(dataset_name_map[ds.lower()])
            elif ds in dataset_name_map.values():
                # Already a full name
                mapped_datasets.append(ds)
            else:
                print(f"⚠️  Warning: Unknown dataset name: {ds}")
        args.datasets = mapped_datasets if mapped_datasets else None

    # Print configuration
    print(f"Configuration:")
    print(f"  Timeout: {args.timeout}ms")
    print(f"  MaxSAT: {'Enabled' if args.maxsat else 'Disabled'}")
    print(f"  Analysis: {'Enabled' if not args.no_analysis else 'Disabled'}")
    if args.approaches:
        print(f"  Approaches: {args.approaches}")
    if args.datasets:
        print(f"  Datasets: {args.datasets}")
    print()

    # Filter constraint sets if specified
    if args.datasets:
        constraint_sets = [cs for cs in constraint_sets if cs["name"] in args.datasets]
        constraint_sets = [cs for cs in constraint_sets if cs["name"] in args.datasets]
        if not constraint_sets:
            print(f"⚠️  Warning: No matching datasets found. Available datasets:")
            print(f"    - legal (Legal Document Constraints)")
            print(f"    - llm (LLM Generated Constraints)")
            print(f"    - grammar (Grammar Constraints)")
            return

    # Run benchmarks for each constraint set
    for constraint_set in constraint_sets:
        name = constraint_set["name"]
        constraints_file = constraint_set["constraints_file"]
        output_dir = constraint_set["output_dir"]

        print(f"{'='*70}")
        print(f"Running: {name}")
        print(f"{'='*70}")
        print(f"Constraints file: {constraints_file}")
        print(f"Output directory: {output_dir}")

        if not constraints_file.exists():
            print(f"⚠️  Skipping - Constraints file not found: {constraints_file}\n")
            continue

        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run constraint execution
        run_constraints_file(
            str(constraints_file),
            str(output_dir),
            args.timeout,
            use_maxsat=args.maxsat,
            approaches=args.approaches,
        )

        # Run analysis if enabled
        if not args.no_analysis:
            print(f"\n{'='*60}")
            print("RUNNING ANALYSIS")
            print(f"{'='*60}")

            results_dir = Path(output_dir)
            if not results_dir.exists() or not results_dir.is_dir():
                print(f"❌ Error: Results directory not found: {results_dir}")
                continue

            # Analyze constraints supported by enumeration baseline
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

            # Handle constraints not supported by enumeration baseline
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
                    f"⚠️  {not_supported_count} constraints without enumeration support "
                    f"(saved to: {unsupported_output})"
                )

            # Print summary statistics
            counts = summary_supported["counts_by_approach"]
            print(f"\nSummary by approach (enumeration supported):")
            for approach, counts_dict in counts.items():
                total = sum(counts_dict.values())
                correct = counts_dict.get("correct", 0)
                percentage = correct / total * 100 if total > 0 else 0
                print(f"  {approach}: {correct}/{total} correct ({percentage:.1f}%)")

        print()  # Blank line between constraint sets


if __name__ == "__main__":
    main()
