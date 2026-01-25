#!/usr/bin/env python3
"""
Utility script to run enumeration baseline on LLM generated constraints.

This script runs the enumeration baseline solver on LLM-generated constraints
and saves the results. The enumeration baseline is kept separate from the main
benchmark script as it requires special handling and doesn't follow the standard
solver API.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datesmt.constraint_parser import ConstraintParser
from datesmt.enumeration_baseline import EnumerationSolver

TIMEOUT_MS = 60000


def run_constraint_with_enumeration(
    constraint_data: dict,
    timeout_ms: int = TIMEOUT_MS,
) -> dict:
    """Run a single constraint with the enumeration baseline solver."""
    constraint_id = constraint_data.get("id", "unknown")
    print(f"\n=== Running {constraint_id} (ENUMERATION BASELINE) ===")
    print(f"Constraint: {constraint_data}")

    result = {
        # Input constraint information
        "id": constraint_id,
        "constraints": constraint_data.get("constraints", []),
        "declarations": constraint_data.get("declarations", []),
        # Execution metadata
        "approach": "enumeration",
        "implementation": "naive",
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "smtlib": None,
    }

    try:
        # Enumeration baseline doesn't use the high-level API
        parser = ConstraintParser()
        constraint_code = parser.parse_constraint_data(constraint_data)

        solver = EnumerationSolver(timeout_ms=timeout_ms)
        exec_globals = solver.get_execution_context()

        start_time = time.time()
        try:
            exec(constraint_code, exec_globals)
        except AttributeError as e:
            error_msg = str(e)
            if "add_bool_var" in error_msg or "add_int_var" in error_msg:
                result["status"] = "not_applicable"
                result["error_message"] = (
                    f"Enumeration baseline does not support these variable types: {error_msg}"
                )
                print(
                    "⚠️  Not applicable: Enumeration baseline doesn't support bool/int variables"
                )
                return result
            raise

        builder = exec_globals.get("result") or exec_globals.get("builder") or solver
        if not builder:
            raise RuntimeError("Constraint code did not create a solver")

        result["smtlib"] = builder.to_smt2()
        solve_result = builder.solve()
        result["execution_time"] = time.time() - start_time

        # Extract status and solution from solve result
        result["status"] = solve_result.get("status", "error")
        result["execution_time"] = solve_result.get(
            "execution_time", result["execution_time"]
        )

        # Merge solution from all variable types
        merged_solution = {}
        for var_type in ["dates", "ints", "bools"]:
            vars_dict = solve_result.get(var_type, {}) or {}
            for name, value in vars_dict.items():
                merged_solution[name] = str(value) if var_type == "dates" else value

        result["solution"] = merged_solution if merged_solution else None

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
        result["error_message"] = str(e)
        result["status"] = "error"
        # Errors that occur before/during solving should have 0.0 execution time
        # to distinguish them from timeouts or successful solves
        result["execution_time"] = 0.0
        print(f"❌ Error: {e}")

    return result


def run_enumeration_on_llm_constraints(
    constraints_file: str,
    output_file: str,
    timeout_ms: int = TIMEOUT_MS,
):
    """Run enumeration baseline on LLM generated constraints."""
    # Load constraints
    with open(constraints_file, "r") as f:
        constraints = json.load(f)
        # If it's a single object, wrap it in a list
        if isinstance(constraints, dict):
            constraints = [constraints]

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")
    print(f"Output file: {output_file}")
    print(f"Timeout: {timeout_ms}ms\n")

    print(f"{'='*60}")
    print("RUNNING ENUMERATION BASELINE")
    print(f"{'='*60}")

    results = []
    for constraint in constraints:
        result = run_constraint_with_enumeration(constraint, timeout_ms)
        results.append(result)

    # Save results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    # Print summary
    total = len(results)
    successful = len([r for r in results if r["status"] == "sat"])
    not_applicable = len([r for r in results if r["status"] == "not_applicable"])
    timeout = len([r for r in results if r["status"] == "timeout"])
    unsat = len([r for r in results if r["status"] == "unsat"])
    error = len([r for r in results if r["status"] == "error"])

    # Calculate average time only for constraints that ran
    ran_results = [r for r in results if r["status"] not in ["not_applicable", "error"]]
    avg_time = (
        sum(r["execution_time"] for r in ran_results) / len(ran_results)
        if ran_results
        else 0
    )

    print(f"\nTotal constraints: {total}")
    print(f"  SAT (successful): {successful} ({successful/total*100:.1f}%)")
    print(f"  UNSAT: {unsat} ({unsat/total*100:.1f}%)")
    print(f"  Timeout: {timeout} ({timeout/total*100:.1f}%)")
    print(f"  Not applicable: {not_applicable} ({not_applicable/total*100:.1f}%)")
    print(f"  Error: {error} ({error/total*100:.1f}%)")
    print(f"  Average time (ran): {avg_time:.4f}s")
    print(f"\nResults saved to: {output_file}")

    return results


def main():
    """Main function to run enumeration baseline on LLM constraints."""
    # Default paths
    SCRIPT_DIR = Path(__file__).parent.parent
    DEFAULT_CONSTRAINTS_FILE = (
        SCRIPT_DIR / "llm_constraints" / "constraints" / "constraints.json"
    )
    DEFAULT_OUTPUT_FILE = (
        SCRIPT_DIR / "llm_constraints" / "results" / "enumeration_naive.json"
    )

    parser = argparse.ArgumentParser(
        description="Run enumeration baseline on LLM generated constraints"
    )
    parser.add_argument(
        "--constraints",
        type=str,
        default=str(DEFAULT_CONSTRAINTS_FILE),
        help=f"Path to constraints file (default: {DEFAULT_CONSTRAINTS_FILE})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_FILE),
        help=f"Path to output file (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_MS,
        help="Timeout in milliseconds (default: 60000 = 60 seconds)",
    )

    args = parser.parse_args()

    constraints_file = Path(args.constraints)
    if not constraints_file.exists():
        print(f"❌ Error: Constraints file not found: {constraints_file}")
        sys.exit(1)

    run_enumeration_on_llm_constraints(
        str(constraints_file),
        args.output,
        timeout_ms=args.timeout,
    )


if __name__ == "__main__":
    main()
