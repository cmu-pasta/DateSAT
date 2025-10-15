"""
Enhanced template file to test generated constraints with both baseline and epoch_days approaches.
Now supports the enhanced schema with coverage tags and expected satisfiability.
"""

import json
import os
import sys
import time
from datetime import datetime

# Ensure repository root is on sys.path so `import datesmt_int` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from datesmt.api import DateSMTBuilder
    from datesmt.concrete import (
        BaselineConcreteSolver,
        ConcreteDateVar,
        ConcretePeriodVar,
    )
    from datesmt.constraint_parser import ConstraintParser
    from datesmt.core import Date, Period
except ImportError:
    # Fallback: attempt to re-add repo root (in case environment modified sys.path)
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from datesmt.api import DateSMTBuilder
    from datesmt.concrete import (
        BaselineConcreteSolver,
        ConcreteDateVar,
        ConcretePeriodVar,
    )
    from datesmt.constraint_parser import ConstraintParser
    from datesmt.core import Date, Period


def _get_constraint_code(constraint_data: dict) -> str:
    """Get constraint code from new format constraint data."""
    parser = ConstraintParser()
    return parser.parse_constraint_data(constraint_data)


def run_constraint_with_approach(
    constraint_data: dict, approach: str, implementation: str, timeout_ms: int = 60000
) -> dict:
    """Run a single constraint with a specific approach and implementation."""

    constraint_id = constraint_data["id"]
    description = constraint_data.get("description", "")
    coverage_tags = constraint_data.get("coverage_tags", [])

    # Get constraint code from new format
    constraint_code = _get_constraint_code(constraint_data)

    # Extract variables from new format
    variables = constraint_data.get("date_variables", []) + constraint_data.get(
        "period_variables", []
    )

    print(
        f"\n=== Running {constraint_id} ({approach.upper()}, {implementation.upper()}) ==="
    )
    print(f"Description: {description}")
    print(f"Coverage tags: {', '.join(coverage_tags)}")
    print(f"Constraint: {constraint_code}")

    result = {
        # New format fields (copied directly from input)
        "id": constraint_id,
        "description": description,
        "constraints": constraint_data.get("constraints", []),
        "date_variables": constraint_data.get("date_variables", []),
        "period_variables": constraint_data.get("period_variables", []),
        "coverage_tags": coverage_tags,
        # Old format fields (for backward compatibility)
        "constraint_id": constraint_id,
        "constraint_code": constraint_code,
        "variables": variables,
        # Execution metadata
        "approach": approach,
        "implementation": implementation,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
    }

    try:
        start_time = time.time()

        # Execute the constraint code (which creates its own builder and variables)
        # This avoids the duplicate constraint issue
        # Create a DateSMTBuilder factory that injects the approach parameter, implementation, and timeout
        def create_builder():
            return DateSMTBuilder(
                approach=approach, implementation=implementation, timeout_ms=timeout_ms
            )

        exec_globals = {
            'Date': Date,
            'Period': Period,
            'DateSMTBuilder': create_builder,
        }

        exec(constraint_code, exec_globals)

        # Get the builder from the executed code
        builder = exec_globals.get('result') or exec_globals.get('builder')
        if not builder:
            raise RuntimeError("Constraint code did not create a builder")

        # Capture SMT-LIB encoding before solving and store it in result
        result["smtlib"] = builder.to_smt2()

        # Solve
        solve_result = builder.solve()

        end_time = time.time()
        result["execution_time"] = end_time - start_time
        result["status"] = solve_result["status"]
        result["solution"] = solve_result.get("dates", {})
        if solve_result.get("periods"):
            result["solution"].update(solve_result["periods"])

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
                    if reason == "timeout" or "timeout" in reason:
                        result["status"] = "timeout"
                        # Preserve the reason for diagnostics
                        if not result.get("error_message"):
                            result["error_message"] = reason
            except Exception:
                # Best-effort; ignore probing errors
                pass

        if result["status"] == "sat":
            print(f"✅ Solution found:")
            for name, date in result["solution"].items():
                print(f"  {name} = {date}")

        elif result["status"] == "timeout":
            print("⏱️ Solver timeout")
        else:
            print(f"❌ No solution found")

    except TypeError as e:
        if (
            "'>' not supported between instances of 'Period' and 'Period'" in str(e)
            or "'<' not supported between instances of 'Period' and 'Period'" in str(e)
            or "'>=' not supported between instances of 'Period' and 'Period'" in str(e)
            or "'<=' not supported between instances of 'Period' and 'Period'" in str(e)
        ):
            result["error_message"] = (
                f"UNSUPPORTED OPERATION: Period comparison is not allowed - {str(e)}"
            )
            result["status"] = "unsupported"
            print(f"🚫 UNSUPPORTED OPERATION: Period comparison detected - {str(e)}")
        else:
            result["error_message"] = str(e)
            print(f"❌ Error: {e}")
    except Exception as e:
        result["error_message"] = str(e)
        print(f"❌ Error: {e}")

    return result


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    import re

    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def run_constraints_file(
    constraints_file: str, output_dir: str = "results_analysis", timeout_ms: int = 60000
):
    """Test all constraints in a file with both approaches and both implementations."""

    # Load constraints
    with open(constraints_file, 'r') as f:
        constraints = json.load(f)

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    smt_dir = os.path.join(output_dir, "smt2")
    os.makedirs(smt_dir, exist_ok=True)

    # Test with all approaches and both implementations
    approaches = ["baseline", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"]
    implementations = ["int", "bitvector"]
    all_results = {}

    for implementation in implementations:
        for approach in approaches:
            print(f"\n{'='*60}")
            print(
                f"TESTING WITH {approach.upper()} APPROACH ({implementation.upper()})"
            )
            print(f"{'='*60}")

            results = []
            for constraint in constraints:
                result = run_constraint_with_approach(
                    constraint, approach, implementation, timeout_ms
                )
                # Save per-constraint SMT-LIB as .smt2 file
                if result.get("smtlib"):
                    cid = _sanitize_filename(result.get("constraint_id", "unknown"))
                    smt_path = os.path.join(
                        smt_dir, f"{cid}_{approach}_{implementation}.smt2"
                    )
                    try:
                        with open(smt_path, 'w') as f:
                            f.write(result["smtlib"])
                        # Attach path for traceability
                        result["smtlib_file"] = smt_path
                    except Exception as e:
                        result["smtlib_file_error"] = str(e)
                results.append(result)

            all_results[f"{approach}_{implementation}"] = results

            # Save results for this approach and implementation
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                output_dir, f"{approach}_{implementation}_{timestamp}.json"
            )
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\nResults saved to: {output_file}")

            # Print summary
            successful = len([r for r in results if r["status"] == "sat"])
            total = len(results)
            avg_time = (
                sum(r["execution_time"] for r in results) / total if total > 0 else 0
            )

            print(f"\nSummary for {approach} ({implementation}):")
            print(f"  Successful: {successful}/{total} ({successful/total*100:.1f}%)")
            print(f"  Avg time: {avg_time:.4f}s")


def main():
    """Main function to run constraint testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test generated constraints with DATE-SMT"
    )
    parser.add_argument(
        "constraints_file", help="JSON file containing generated constraints"
    )
    parser.add_argument(
        "--output-dir", default="results_analysis", help="Output directory for results"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60000,
        help="Timeout in milliseconds (default: 60000 = 60 seconds)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.constraints_file):
        print(f"Error: Constraints file {args.constraints_file} not found")
        return

    run_constraints_file(args.constraints_file, args.output_dir, args.timeout)


if __name__ == "__main__":
    main()
