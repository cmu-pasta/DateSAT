import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dataset.validation import check_results_dir
from datesmt.api import DateSMTBuilder
from datesmt.constraint_parser import ConstraintParser
from datesmt.core import Date, Period
from datesmt.enumeration_baseline import EnumerationSolver

TIMEOUT_MS = 10000


def run_constraint_with_approach(
    constraint_data: dict,
    approach: str,
    implementation: str,
    timeout_ms: int = TIMEOUT_MS,
) -> dict:
    """Run a single constraint with a specific approach and implementation."""
    constraint_id = constraint_data["id"]
    print(
        f"\n=== Running {constraint_id} ({approach.upper()}, {implementation.upper()}) ==="
    )

    # Get constraint code from new format
    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)

    print(f"Constraint: {constraint_code}")

    result = {
        # New format fields (copied directly from input)
        "id": constraint_id,
        "constraints": constraint_data.get("constraints", []),
        "declarations": constraint_data.get("declarations", []),
        # Execution metadata
        "approach": approach,
        "implementation": implementation,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
    }

    start_time = time.time()
    try:
        # Handle enumeration baseline differently (it doesn't use DateSMTBuilder)
        if approach == "enumeration":
            # Create EnumerationSolver directly
            solver = EnumerationSolver(timeout_ms=timeout_ms)
            exec_globals = solver.get_execution_context()

            try:
                exec(constraint_code, exec_globals)
            except AttributeError as e:
                error_msg = str(e)
                # Treat unhandled add_bool_var/add_int_var as not supported
                if "add_bool_var" in error_msg or "add_int_var" in error_msg:
                    result["status"] = "not_applicable"
                    result["error_message"] = (
                        "Enumeration baseline does not support these variable types: "
                        f"{error_msg}"
                    )
                    result["solution"] = None
                    result["smtlib"] = None
                    print("Not applicable: Enumeration baseline doesn't support bool/int variables")
                    return result
                raise

            # Get the solver from the executed code
            builder = exec_globals.get("result") or exec_globals.get("builder") or solver
            if not builder:
                raise RuntimeError("Constraint code did not create a solver")

            # Enumeration baseline doesn't generate SMT-LIB
            result["smtlib"] = builder.to_smt2()

            # Solve
            solve_result = builder.solve()

        else:
            # Execute the constraint code (which creates its own builder and variables)
            # This avoids the duplicate constraint issue
            # Create a DateSMTBuilder factory that injects the approach parameter, implementation, and timeout
            def create_builder():
                return DateSMTBuilder(
                    approach=approach,
                    implementation=implementation,
                    timeout_ms=timeout_ms,
                )

            exec_globals = {
                "Date": Date,
                "Period": Period,
                "DateSMTBuilder": create_builder,
            }

            exec(constraint_code, exec_globals)

            # Get the builder from the executed code
            builder = exec_globals.get("result") or exec_globals.get("builder")
            if not builder:
                raise RuntimeError("Constraint code did not create a builder")

            # Capture SMT-LIB encoding before solving and store it in result
            result["smtlib"] = builder.to_smt2()

            # Solve
            solve_result = builder.solve()

        result["status"] = solve_result["status"]

        # Detect Z3 timeout and normalize status to "timeout" instead of mislabeling as unsat
        if result["status"] != "sat":
            try:
                # Access underlying z3.Solver via builder.solver.solver
                solver_wrapper = getattr(builder, "solver", None)
                z3_solver = getattr(solver_wrapper, "solver", None)
                if z3_solver is not None:
                    reason = (
                        str(getattr(z3_solver, "reason_unknown", lambda: "")())
                        .strip()
                        .lower()
                    )
                    if "timeout" in reason:
                        result["status"] = "timeout"
                        # Preserve the reason for diagnostics
                        if not result.get("error_message"):
                            result["error_message"] = reason
            except Exception:
                # Best-effort; ignore probing errors
                pass

        # Include all variable types in the stored solution
        solution_dates = solve_result.get("dates", {}) or {}
        solution_ints = solve_result.get("ints", {}) or {}
        solution_bools = solve_result.get("bools", {}) or {}
        merged_solution = {}
        merged_solution.update({k: str(v) for k, v in solution_dates.items()})
        merged_solution.update({k: v for k, v in solution_ints.items()})
        merged_solution.update({k: v for k, v in solution_bools.items()})
        result["solution"] = merged_solution

        if result["status"] == "sat":
            print(f"✅ Solution found:")
            for name, date in result["solution"].items():
                print(f"  {name} = {date}")

        elif result["status"] == "timeout":
            print("⏱️ Solver timeout")
        else:
            print(f"❌ No solution found")
    except Exception as e:
        result["error_message"] = str(e)
        print(f"❌ Error: {e}")
    finally:
        # Set execution_time
        end_time = time.time()
        result["execution_time"] = end_time - start_time

    return result


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def run_constraints_file(
    constraints_file: str,
    output_dir: str,
    timeout_ms: int = TIMEOUT_MS,
):
    # Load constraints - support both JSON and JSONL formats
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
                    print(f"Warning: Skipping invalid JSON on line {line_num} of {constraints_file}: {e}")
                    continue
    else:
        # JSON format: single JSON array/object
        with open(constraints_file, "r") as f:
            constraints = json.load(f)
            # If it's a single object, wrap it in a list
            if isinstance(constraints, dict):
                constraints = [constraints]

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")
    print(f"Output directory: {output_dir}")

    smt_dir = os.path.join(output_dir, "smt_constraints")
    os.makedirs(smt_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Define all methods to run
    baseline_approaches = ["enumeration"]
    symbolic_approaches = [
        "naive",
        "epoch_days",
        "hybrid",
        "alpha_beta",
        "alpha_beta_table",
    ]
    implementations = ["int", "bitvector"]

    # Unify all methods into a single list
    # Symbolic approaches with int/bitvector implementations
    all_methods = [
        (approach, impl) for approach in symbolic_approaches for impl in implementations
    ]
    # Baseline approaches with "naive" implementation
    all_methods.extend([(approach, "naive") for approach in baseline_approaches])

    all_results = {}

    # Run all approaches with their respective implementations
    for approach, implementation in all_methods:
        print(f"\n{'='*60}")
        print(f"TESTING WITH {approach.upper()} APPROACH ({implementation.upper()})")
        print(f"{'='*60}")

        results = []
        for constraint in constraints:
            result = run_constraint_with_approach(
                constraint, approach, implementation, timeout_ms
            )

            # Save per-constraint SMT-LIB as .smt2 file
            if result.get("smtlib"):
                cid = _sanitize_filename(result.get("id", "unknown"))
                smt_path = os.path.join(
                    smt_dir, f"{cid}_{approach}_{implementation}.smt2"
                )
                try:
                    with open(smt_path, "w") as f:
                        f.write(result["smtlib"])
                    # Attach path for traceability
                    result["smtlib_file"] = smt_path
                except Exception as e:
                    result["smtlib_file_error"] = str(e)

            results.append(result)

        all_results[f"{approach}_{implementation}"] = results

        # Save results for this approach and implementation
        output_file = os.path.join(output_dir, f"{approach}_{implementation}.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")

        # Print summary
        successful = len([r for r in results if r["status"] == "sat"])
        total = len(results)
        avg_time = sum(r["execution_time"] for r in results) / total if total > 0 else 0

        print(f"\nSummary for {approach} ({implementation}):")
        print(f"  Successful: {successful}/{total} ({successful/total*100:.1f}%)")
        print(f"  Avg time: {avg_time:.4f}s")

    return all_results


# =========================
# Results Analysis
# =========================
# Note: Analysis functions have been moved to dataset.validation


def main():
    """Main function to run constraint testing and analysis."""
    # Predetermined paths for both constraint sets
    SCRIPT_DIR = Path(__file__).parent

    constraint_sets = [
        # {
        #     "name": "Grammar Constraints",
        #     "constraints_file": SCRIPT_DIR
        #     / "grammar_constraints"
        #     / "constraints"
        #     / "constraints.json",
        #     "output_dir": SCRIPT_DIR / "grammar_constraints" / "results",
        # },
        #{
        #    "name": "LLM Generated Constraints",
        #    "constraints_file": SCRIPT_DIR
        #    / "llm_constraints"
        #    / "constraints"
        #    / "constraints.json",
        #    "output_dir": SCRIPT_DIR / "llm_constraints" / "results",
        #},
        {
            "name": "Legal Document Constraints",
            "constraints_file": SCRIPT_DIR
            / "legal_doc_constraints"
            / "constraints"
            / "constraints.jsonl",
            "output_dir": SCRIPT_DIR / "legal_doc_constraints" / "results",
        },
    ]

    parser = argparse.ArgumentParser(
        description="Test generated constraints with DATE-SMT and optionally analyze results"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_MS,
        help="Timeout in milliseconds (default: 10000 = 10 seconds)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip analysis after constraint execution (default: run analysis)",
    )

    args = parser.parse_args()

    print(f"Analysis: {'Enabled' if not args.no_analysis else 'Disabled'}")
    print(f"Timeout: {args.timeout}ms\n")

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

        # Run constraint execution
        run_constraints_file(
            str(constraints_file), str(output_dir), args.timeout
        )

        if not args.no_analysis:
            print(f"\n{'='*60}")
            print("RUNNING ANALYSIS")
            print(f"{'='*60}")

            results_dir = Path(output_dir)

            if not results_dir.exists() or not results_dir.is_dir():
                print(f"Error: Results directory not found: {results_dir}")
                continue

            summary_supported = check_results_dir(
                results_dir, enumeration_filter="supported"
            )

            # Save analysis results for constraints supported by enumeration baseline
            analysis_output = results_dir / "checked_summary_with_baseline.json"
            with open(analysis_output, "w", encoding="utf-8") as f:
                json.dump(summary_supported, f, indent=2, sort_keys=False)

            print(f"\nAnalysis complete!")
            print(
                f"Checked {summary_supported['constraints_checked']} constraints "
                "(enumeration supported)"
            )
            print(f"Analysis results saved to: {analysis_output}")

            # If there are constraints the enumeration baseline does not support,
            # save their stats separately.
            enum_support = summary_supported.get("enumeration_support", {})
            not_supported_count = enum_support.get("not_supported_count", 0)
            if not_supported_count:
                unsupported_summary = check_results_dir(
                    results_dir, enumeration_filter="not_supported"
                )
                unsupported_output = results_dir / "checked_summary_without_baseline.json"
                with open(unsupported_output, "w", encoding="utf-8") as f:
                    json.dump(unsupported_summary, f, indent=2, sort_keys=False)
                print(
                    f"Constraints without enumeration support: {not_supported_count} "
                    f"(saved to: {unsupported_output})"
                )

            # Print summary statistics for supported constraints
            counts = summary_supported["counts_by_approach"]
            print(f"\nSummary by approach (enumeration supported constraints):")
            for approach, counts_dict in counts.items():
                total = sum(counts_dict.values())
                correct = counts_dict.get("correct", 0)
                print(
                    f"  {approach}: {correct}/{total} correct ({correct/total*100:.1f}%)"
                )

        print()  # Blank line between constraint sets


if __name__ == "__main__":
    main()
