"""
Enhanced test runner that combines constraint execution and analysis.
Supports both running constraints and analyzing results with concrete validation.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path so `import datesmt_int` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from datesmt.api import DateSMTBuilder
    from datesmt.constraint_parser import ConstraintParser
    from datesmt.core import Date, Period
    from datesmt.enumeration_baseline import EnumerationSolver, EnumerationDateVar
    from dataset.validation import (
        check_results_dir,
        parse_date_string,
        parse_period_string,
        validate_solution_with_concrete,
    )
except ImportError:
    # Fallback: attempt to re-add repo root (in case environment modified sys.path)
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from datesmt.api import DateSMTBuilder
    from datesmt.constraint_parser import ConstraintParser
    from datesmt.core import Date, Period
    from datesmt.enumeration_baseline import EnumerationSolver, EnumerationDateVar
    from dataset.validation import (
        check_results_dir,
        parse_date_string,
        parse_period_string,
        validate_solution_with_concrete,
    )


# =========================
# Constraint Execution
# =========================

def _get_constraint_code(constraint_data: dict) -> str:
    """Get constraint code from new format constraint data."""
    parser = ConstraintParser()
    return parser.parse_constraint_data(constraint_data)


def run_constraint_with_approach(
    constraint_data: dict, approach: str, implementation: str, timeout_ms: int = 600000
) -> dict:
    """Run a single constraint with a specific approach and implementation."""

    constraint_id = constraint_data["id"]
    description = constraint_data.get("description", "")
    coverage_tags = constraint_data.get("coverage_tags", [])

    result = {
        # New format fields (copied directly from input)
        "id": constraint_id,
        "description": description,
        "constraints": constraint_data.get("constraints", []),
        "coverage_tags": coverage_tags,
        # Old format fields (for backward compatibility)
        "constraint_id": constraint_id,
        "constraint_code": None,
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
        # Get constraint code from new format (inside try block to catch parsing errors)
        constraint_code = _get_constraint_code(constraint_data)
        result["constraint_code"] = constraint_code

        print(
            f"\n=== Running {constraint_id} ({approach.upper()}, {implementation.upper()}) ==="
        )
        print(f"Description: {description}")
        print(f"Coverage tags: {', '.join(coverage_tags)}")
        print(f"Constraint: {constraint_code}")

        # Handle enumeration baseline differently (it doesn't use DateSMTBuilder)
        if approach == "enumeration":
            # Create EnumerationSolver directly
            def create_builder():
                return EnumerationSolver(timeout_ms=timeout_ms)

            exec_globals = {
                'Date': Date,
                'Period': Period,
                'DateSMTBuilder': create_builder,
            }

            exec(constraint_code, exec_globals)

            # Get the solver from the executed code
            builder = exec_globals.get('result') or exec_globals.get('builder')
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
        
        # Detect Z3 timeout and normalize status to "timeout" instead of mislabeling as unsat
        # This check applies to both enumeration and symbolic approaches
        # When Z3 times out, check() returns unknown, but solve() methods may return "unsat"
        # So we need to check Z3's reason_unknown to detect actual timeouts
        if result["status"] == "unsat" or result["status"] not in ["sat", "timeout"]:
            try:
                # For symbolic approaches, check Z3's reason_unknown
                if approach != "enumeration":
                    solver_wrapper = getattr(builder, "solver", None)
                    z3_solver = getattr(solver_wrapper, "solver", None)
                    if z3_solver is not None:
                        # Check Z3's reason_unknown - this is set when check() returns unknown
                        # reason_unknown() is a method that returns the reason string
                        try:
                            reason = str(z3_solver.reason_unknown()).strip().lower()
                            if reason == "timeout" or "timeout" in reason:
                                result["status"] = "timeout"
                                # Preserve the reason for diagnostics
                                if not result.get("error_message"):
                                    result["error_message"] = reason
                        except (AttributeError, TypeError):
                            # If reason_unknown is not available or not callable, try as attribute
                            try:
                                reason = str(getattr(z3_solver, "reason_unknown", "")).strip().lower()
                                if reason == "timeout" or "timeout" in reason:
                                    result["status"] = "timeout"
                                    if not result.get("error_message"):
                                        result["error_message"] = reason
                            except Exception:
                                pass
                # For enumeration, solve_result should already have correct status
                # but we check solve_result directly just in case
                elif "timeout" in str(solve_result.get("reason", "")).lower():
                    result["status"] = "timeout"
            except Exception:
                # Best-effort; ignore probing errors
                pass
        result["solution"] = solve_result.get("dates", {})
        if solve_result.get("periods"):
            result["solution"].update(solve_result["periods"])

        if result["status"] == "sat":
            print(f"✅ Solution found:")
            for name, date in result["solution"].items():
                print(f"  {name} = {date}")

        elif result["status"] == "timeout":
            print("⏱️ Solver timeout")
        else:
            print(f"❌ No solution found")

    except ValueError as e:
        # Handle parsing errors (e.g., unsupported operations in constraints)
        end_time = time.time()
        result["execution_time"] = end_time - start_time
        error_str = str(e)
        if "Could not parse constraint" in error_str:
            result["status"] = "parse_error"
            result["error_message"] = error_str
            print(f"🚫 PARSE ERROR: {error_str}")
        else:
            result["error_message"] = error_str
            print(f"❌ Error: {e}")
    except TimeoutError as e:
        end_time = time.time()
        result["execution_time"] = end_time - start_time
        result["status"] = "timeout"
        result["error_message"] = str(e)
        print(f"⏱️ Timeout: {e}")
    except TypeError as e:
        end_time = time.time()
        result["execution_time"] = end_time - start_time
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
        end_time = time.time()
        result["execution_time"] = end_time - start_time
        result["error_message"] = str(e)
        print(f"❌ Error: {e}")
    finally:
        # Ensure execution_time is always set, even if an exception occurred before it was calculated
        # This is a safety net in case execution_time wasn't set in any exception handler
        if result["execution_time"] == 0:
            end_time = time.time()
            result["execution_time"] = end_time - start_time

    return result


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    import re

    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def parse_method_spec(method_spec: str) -> tuple:
    """
    Parse a method specification string into (approach, implementation).

    Examples:
        "baseline_bitvector" -> ("baseline", "bitvector")
        "enumeration" -> ("enumeration", "baseline")
        "baseline" -> ("baseline", None)  # all implementations
        "bitvector" -> (None, "bitvector")  # all approaches with bitvector

    Returns:
        (approach, implementation) tuple where either can be None to mean "all"
    """
    if not method_spec:
        return (None, None)

    # Check if it's a baseline approach (enumeration)
    if method_spec == "enumeration":
        return (method_spec, "baseline")

    # Check if it's just an implementation type
    if method_spec in ["int", "bitvector"]:
        return (None, method_spec)

    # Check if it's approach_implementation format
    if "_" in method_spec:
        parts = method_spec.split("_", 1)
        if len(parts) == 2:
            approach, implementation = parts
            if approach in ["baseline", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"]:
                if implementation in ["int", "bitvector"]:
                    return (approach, implementation)

    # Check if it's just an approach name
    if method_spec in ["baseline", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"]:
        return (method_spec, None)

    # Invalid format
    raise ValueError(f"Invalid method specification: {method_spec}. "
                     f"Expected format: 'approach_implementation' (e.g., 'baseline_bitvector'), "
                     f"'approach' (e.g., 'baseline'), 'implementation' (e.g., 'bitvector'), "
                     f"or 'enumeration'")


def filter_methods(methods: Optional[List[str]] = None) -> tuple:
    """
    Filter which approaches and implementations to run based on method specifications.

    Args:
        methods: List of method specifications (e.g., ["baseline_bitvector", "enumeration"])
                 If None or empty, returns all methods.

    Returns:
        (symbolic_methods, baseline_methods) where:
        - symbolic_methods: List of (approach, implementation) tuples
        - baseline_methods: List of baseline approach names
    """
    symbolic_approaches = ["baseline", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"]
    baseline_approaches = ["enumeration"]
    implementations = ["int", "bitvector"]

    # If no methods specified, return all
    if not methods:
        symbolic_methods = [
            (approach, impl) for approach in symbolic_approaches for impl in implementations
        ]
        baseline_methods = baseline_approaches
        return (symbolic_methods, baseline_methods)

    # Parse method specifications
    parsed_methods = []
    for method_spec in methods:
        try:
            parsed_methods.append(parse_method_spec(method_spec))
        except ValueError as e:
            print(f"Warning: {e}")
            continue

    # Build filtered lists
    symbolic_methods = []
    baseline_methods = []

    for approach, implementation in parsed_methods:
        if approach in baseline_approaches:
            # Baseline approach
            if approach not in baseline_methods:
                baseline_methods.append(approach)
        elif approach in symbolic_approaches:
            # Symbolic approach
            if implementation is None:
                # All implementations for this approach
                for impl in implementations:
                    if (approach, impl) not in symbolic_methods:
                        symbolic_methods.append((approach, impl))
            elif implementation in implementations:
                # Specific implementation
                if (approach, implementation) not in symbolic_methods:
                    symbolic_methods.append((approach, implementation))
        elif approach is None and implementation in implementations:
            # All approaches with this implementation
            for appr in symbolic_approaches:
                if (appr, implementation) not in symbolic_methods:
                    symbolic_methods.append((appr, implementation))

    return (symbolic_methods, baseline_methods)


def run_constraints_file(
    constraints_file: str, output_dir: str = "results", timeout_ms: int = 600000,
    methods: Optional[List[str]] = None
):
    """Test all constraints in a file with specified approaches and implementations.

    Args:
        constraints_file: Path to JSON file containing constraints
        output_dir: Output directory for results
        timeout_ms: Timeout in milliseconds
        methods: Optional list of method specifications to run. If None, runs all methods.
                 Examples: ["baseline_bitvector", "enumeration", "epoch_days_int"]
    """

    # Load constraints
    with open(constraints_file, 'r') as f:
        constraints = json.load(f)

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    smt_dir = os.path.join(output_dir, "smt2")
    os.makedirs(smt_dir, exist_ok=True)

    # Get filtered methods to run
    symbolic_methods, baseline_methods = filter_methods(methods)

    if not symbolic_methods and not baseline_methods:
        print("Warning: No valid methods specified. Running all methods.")
        symbolic_methods, baseline_methods = filter_methods(None)

    print(f"\nSelected methods to run:")
    if symbolic_methods:
        print(f"  Symbolic approaches: {', '.join([f'{a}_{i}' for a, i in symbolic_methods])}")
    if baseline_methods:
        print(f"  Baseline approaches: {', '.join(baseline_methods)}")

    all_results = {}

    # Run symbolic approaches with specified implementations
    for approach, implementation in symbolic_methods:
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

    # Run baseline approaches (enumeration) - no implementation distinction
    for approach in baseline_methods:
        print(f"\n{'='*60}")
        print(f"TESTING WITH {approach.upper()} BASELINE")
        print(f"{'='*60}")

        results = []
        for constraint in constraints:
            # Baseline approaches don't have implementation, use "baseline" as placeholder
            result = run_constraint_with_approach(
                constraint, approach, "baseline", timeout_ms
            )
            # Save per-constraint SMT-LIB as .smt2 file (will be empty for baselines)
            if result.get("smtlib"):
                cid = _sanitize_filename(result.get("constraint_id", "unknown"))
                smt_path = os.path.join(
                    smt_dir, f"{cid}_{approach}_baseline.smt2"
                )
                try:
                    with open(smt_path, 'w') as f:
                        f.write(result["smtlib"])
                    # Attach path for traceability
                    result["smtlib_file"] = smt_path
                except Exception as e:
                    result["smtlib_file_error"] = str(e)
            results.append(result)

        all_results[f"{approach}_baseline"] = results

        # Save results for this baseline
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            output_dir, f"{approach}_baseline_{timestamp}.json"
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

        print(f"\nSummary for {approach} baseline:")
        print(f"  Successful: {successful}/{total} ({successful/total*100:.1f}%)")
        print(f"  Avg time: {avg_time:.4f}s")

    return all_results


# =========================
# Results Analysis
# =========================
# Note: Analysis functions have been moved to dataset.validation


# =========================
# Main Function
# =========================

def main():
    """Main function to run constraint testing and analysis."""
    parser = argparse.ArgumentParser(
        description="Test generated constraints with DATE-SMT and optionally analyze results"
    )
    parser.add_argument(
        "constraints_file", help="JSON file containing generated constraints"
    )
    parser.add_argument(
        "--output-dir", default="results", help="Output directory for results"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600000,
        help="Timeout in milliseconds (default: 600000 = 10 minutes)",
    )
    parser.add_argument(
        "--analysis",
        action="store_true",
        default=True,
        help="Run analysis after constraint execution (default: True)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip analysis and only run constraint execution",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        default=None,
        help="Select specific methods to run. Can specify multiple methods. "
             "Examples: --methods baseline_bitvector enumeration (run only baseline_bitvector and enumeration), "
             "--methods bitvector (run all bitvector implementations), "
             "--methods baseline (run baseline with both int and bitvector). "
             "Default: run all methods. "
             "Format: 'approach_implementation' (e.g., 'baseline_bitvector'), "
             "'approach' (e.g., 'baseline'), 'implementation' (e.g., 'bitvector'), "
             "or 'enumeration'",
    )

    args = parser.parse_args()

    if not os.path.exists(args.constraints_file):
        print(f"Error: Constraints file {args.constraints_file} not found")
        return

    # Determine if analysis should run
    run_analysis = args.analysis and not args.no_analysis

    print(f"Running constraint tests...")
    print(f"Analysis: {'Enabled' if run_analysis else 'Disabled'}")
    if args.methods:
        print(f"Methods: {', '.join(args.methods)}")
    else:
        print(f"Methods: All methods (default)")

    # Run constraint execution
    all_results = run_constraints_file(
        args.constraints_file, args.output_dir, args.timeout, methods=args.methods
    )

    if run_analysis:
        print(f"\n{'='*60}")
        print("RUNNING ANALYSIS")
        print(f"{'='*60}")

        results_dir = Path(args.output_dir)
        if not results_dir.exists() or not results_dir.is_dir():
            print(f"Error: Results directory not found: {results_dir}")
            return

        summary = check_results_dir(results_dir)

        # Save analysis results
        analysis_output = results_dir / "checked_summary.json"
        with open(analysis_output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=False)

        print(f"\nAnalysis complete!")
        print(f"Checked {summary['constraints_checked']} constraints")
        print(f"Analysis results saved to: {analysis_output}")

        # Print summary statistics
        counts = summary['counts_by_approach']
        print(f"\nSummary by approach:")
        for approach, counts_dict in counts.items():
            total = sum(counts_dict.values())
            correct = counts_dict.get('correct', 0)
            print(f"  {approach}: {correct}/{total} correct ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()
