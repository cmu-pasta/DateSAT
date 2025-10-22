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
    from tests.integration_tests.validation import (
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
    from tests.integration_tests.validation import (
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
    constraint_data: dict, approach: str, implementation: str, timeout_ms: int = 60000
) -> dict:
    """Run a single constraint with a specific approach and implementation."""

    constraint_id = constraint_data["id"]
    description = constraint_data.get("description", "")
    coverage_tags = constraint_data.get("coverage_tags", [])

    # Get constraint code from new format
    constraint_code = _get_constraint_code(constraint_data)

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
        "coverage_tags": coverage_tags,
        # Old format fields (for backward compatibility)
        "constraint_id": constraint_id,
        "constraint_code": constraint_code,
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
    constraints_file: str, output_dir: str = "results", timeout_ms: int = 60000
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

    return all_results


# =========================
# Results Analysis
# =========================

def load_results_files(results_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    # Look for both old pattern (results_*.json) and new pattern (*_*.json)
    for pattern in ["results_*.json", "*_*.json"]:
        for path in sorted(results_dir.glob(pattern)):
            # Skip SMT2 files
            if path.suffix == '.smt2':
                continue
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records.extend(data)
    return records


def group_by_constraint(
    records: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]:
    """
    Groups records by constraint_id, then by approach, then by implementation.
    Structure: {constraint_id: {approach: {implementation: record}}}
    """
    grouped: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
    for rec in records:
        cid = rec.get("constraint_id")
        approach = rec.get("approach")
        implementation = rec.get("implementation", "unknown")
        if not cid or not approach:
            # Skip malformed entries
            continue
        grouped.setdefault(cid, {}).setdefault(approach, {})[implementation] = rec
    return grouped


def validate_sat_record(
    constraint_id: str, rec: Dict[str, Any], save_dir: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Validates the provided sat solution using concrete implementation.

    Returns:
      (is_valid, message)
    """
    approach = rec.get("approach")
    solution = rec.get("solution") or {}
    constraint_code = rec.get("constraint_code", "")

    if not isinstance(solution, dict) or not solution:
        return False, "missing or empty solution map"

    if not constraint_code:
        return False, "missing constraint code"

    # Construct constraint data from new format fields for validation
    constraint_data = {
        "constraints": rec.get("constraints", []),
        "coverage_tags": rec.get("coverage_tags", []),
    }

    # Use concrete validation from validation.py
    is_valid, message = validate_solution_with_concrete(
        constraint_data, solution, constraint_id, save_dir
    )

    if save_dir is not None:
        # Save a note about using concrete validation
        out_file = save_dir / f"{constraint_id}_{approach}_concrete_validation.txt"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as f:
            f.write(f"Concrete validation for {constraint_id} ({approach})\n")
            f.write(f"Valid: {is_valid}\n")
            f.write(f"Message: {message}\n")
            f.write(f"Solution: {solution}\n")

    return is_valid, message


def summarize_constraint(
    cid: str,
    approaches: Dict[str, Dict[str, Dict[str, Any]]],
    save_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    # Flatten the nested structure for backward compatibility
    flattened_approaches: Dict[str, Dict[str, Any]] = {}
    for approach, implementations in approaches.items():
        for implementation, record in implementations.items():
            # Create a composite key for approach + implementation
            key = f"{approach}_{implementation}"
            flattened_approaches[key] = record

    approach_statuses: Dict[str, str] = {
        a: r.get("status", "unknown") for a, r in flattened_approaches.items()
    }
    sat_recs = {
        a: r for a, r in flattened_approaches.items() if r.get("status") == "sat"
    }
    unsat_recs = {
        a: r for a, r in flattened_approaches.items() if r.get("status") == "unsat"
    }

    # For description, pick SAT one if any, else any
    any_rec = next(iter(sat_recs.values()), next(iter(flattened_approaches.values())))
    description = any_rec.get("description")

    # Validate SAT records by actually pinning and checking
    sat_validation: Dict[str, Dict[str, Any]] = {}
    for a, r in sat_recs.items():
        ok, msg = validate_sat_record(cid, r, save_dir=save_dir)
        sat_validation[a] = {"valid": ok, "message": msg, "solution": r.get("solution")}

    # Decide verdicts per policy, per-approach
    # Original all-unsat consensus across ALL approaches
    all_unsat = len(approach_statuses) > 0 and all(
        s == "unsat" for s in approach_statuses.values()
    )
    # New: UNSAT consensus ignoring timeouts (treat timeouts as neutral/ignored)
    non_timeout_statuses = [s for s in approach_statuses.values() if s != "timeout"]
    unsat_consensus_ignoring_timeouts = len(non_timeout_statuses) > 0 and all(
        s == "unsat" for s in non_timeout_statuses
    )
    any_sat = bool(sat_recs)
    per_approach_verdict: Dict[str, str] = {}

    for a, status in approach_statuses.items():
        if status == "error":
            per_approach_verdict[a] = "error"
        elif status == "timeout":
            # Distinct verdict for timeouts so we can tally separately
            per_approach_verdict[a] = "timeout"
        elif status == "sat":
            vinfo = sat_validation.get(a)
            if vinfo and vinfo.get("valid"):
                per_approach_verdict[a] = "correct"
            else:
                # a sat that does not validate
                per_approach_verdict[a] = "wrong"
        elif status == "unsat":
            # Treat as correct if every non-timeout approach reported UNSAT
            per_approach_verdict[a] = (
                "correct"
                if (all_unsat or unsat_consensus_ignoring_timeouts)
                else "wrong"
            )
        else:
            per_approach_verdict[a] = "wrong"

    # Retain aggregate verdict fields for backward-compatibility
    any_error = any(s == "error" for s in approach_statuses.values())
    if any_error and not any_sat and not all_unsat:
        verdict = "error"
        unsat_consensus = False
        wrong_approaches = [a for a, v in per_approach_verdict.items() if v == "wrong"]
        might_correct_approaches = []
    elif (all_unsat or unsat_consensus_ignoring_timeouts) and not any_sat:
        verdict = "correct_unsat"
        # Expose consensus flag as true when timeouts are ignored and the rest agree on UNSAT
        unsat_consensus = True
        wrong_approaches = []
        might_correct_approaches = []
    else:
        # Aggregate to "correct" if all are correct/correct_unsat; else "wrong" if any wrong; else "correct" if at least one correct
        if all(v in ("correct",) for v in per_approach_verdict.values()):
            verdict = "correct"
        elif any(v == "wrong" for v in per_approach_verdict.values()):
            verdict = "wrong"
        else:
            verdict = "correct"
        unsat_consensus = all_unsat or unsat_consensus_ignoring_timeouts
        wrong_approaches = [a for a, v in per_approach_verdict.items() if v == "wrong"]
        might_correct_approaches = []

    return {
        "constraint_id": cid,
        "description": description,
        "approach_statuses": approach_statuses,
        "sat_validation": sat_validation,  # per-sat approach validity and messages
        "unsat_consensus": unsat_consensus,
        "verdicts_by_approach": per_approach_verdict,  # per-approach: "correct" | "wrong" | "error"
        "wrong_approaches": wrong_approaches,
        "might_correct_approaches": might_correct_approaches,
    }


def check_results_dir(results_dir: Path) -> Dict[str, Any]:
    records = load_results_files(results_dir)
    grouped = group_by_constraint(records)

    summaries: List[Dict[str, Any]] = []
    counts_by_approach: Dict[str, Dict[str, int]] = {}
    save_dir = results_dir / "smt2_assertion"
    save_dir.mkdir(parents=True, exist_ok=True)

    for cid, approaches in sorted(grouped.items(), key=lambda kv: kv[0]):
        summary = summarize_constraint(cid, approaches, save_dir=save_dir)
        summaries.append(summary)
        per = summary.get("verdicts_by_approach", {})
        for approach, v in per.items():
            if approach not in counts_by_approach:
                counts_by_approach[approach] = {
                    "correct": 0,
                    "wrong": 0,
                    "error": 0,
                    "timeout": 0,
                }
            if v in counts_by_approach[approach]:
                counts_by_approach[approach][v] += 1

    # --------------------------
    # Metrics: constraint lines and execution time
    # --------------------------
    def _smt2_lines(fp: Optional[str]) -> int:
        if not fp:
            return 0
        p = Path(fp)
        if not p.is_absolute():
            # smtlib_file paths in results are typically repo-relative
            p = Path(REPO_ROOT) / p
        try:
            with p.open("r", encoding="utf-8") as f:
                # Count non-empty lines; fall back to total lines if all blank
                lines = f.readlines()
                non_empty = [ln for ln in lines if ln.strip()]
                return len(non_empty) if non_empty else len(lines)
        except Exception:
            return 0

    per_constraint_metrics: Dict[str, Dict[str, Any]] = {}
    # Per-approach accumulators
    approach_line_sum: Dict[str, int] = {}
    approach_time_sum: Dict[str, float] = {}
    approach_counts: Dict[str, int] = {}

    # Per-implementation accumulators for int vs bitvector comparison
    implementation_line_sum: Dict[str, int] = {}
    implementation_time_sum: Dict[str, float] = {}
    implementation_counts: Dict[str, int] = {}

    for cid, appr_map in grouped.items():
        entries = []
        for approach, implementations in appr_map.items():
            for implementation, rec in implementations.items():
                smt_path = rec.get("smtlib_file")
                lines = _smt2_lines(smt_path)
                t = float(rec.get("execution_time") or 0.0)

                # Create composite key for approach + implementation
                composite_key = f"{approach}_{implementation}"
                entries.append(
                    {
                        "approach": approach,
                        "implementation": implementation,
                        "composite_key": composite_key,
                        "lines": lines,
                        "execution_time": t,
                    }
                )

                # Update approach-level metrics
                approach_line_sum[approach] = approach_line_sum.get(approach, 0) + lines
                approach_time_sum[approach] = approach_time_sum.get(approach, 0.0) + t
                approach_counts[approach] = approach_counts.get(approach, 0) + 1

                # Update implementation-level metrics
                implementation_line_sum[implementation] = (
                    implementation_line_sum.get(implementation, 0) + lines
                )
                implementation_time_sum[implementation] = (
                    implementation_time_sum.get(implementation, 0.0) + t
                )
                implementation_counts[implementation] = (
                    implementation_counts.get(implementation, 0) + 1
                )

        lines_sorted = sorted(
            [
                {
                    "approach": e["approach"],
                    "implementation": e["implementation"],
                    "lines": e["lines"],
                }
                for e in entries
            ],
            key=lambda x: (x["lines"], x["approach"], x["implementation"]),
        )
        time_sorted = sorted(
            [
                {
                    "approach": e["approach"],
                    "implementation": e["implementation"],
                    "execution_time": e["execution_time"],
                }
                for e in entries
            ],
            key=lambda x: (x["execution_time"], x["approach"], x["implementation"]),
        )

        avg_lines = (
            float(sum(e["lines"] for e in entries)) / len(entries) if entries else 0.0
        )
        avg_time = (
            float(sum(e["execution_time"] for e in entries)) / len(entries)
            if entries
            else 0.0
        )

        per_constraint_metrics[cid] = {
            "lines_by_approach": lines_sorted,
            "time_by_approach": time_sorted,
            "avg_lines": avg_lines,
            "avg_time": avg_time,
        }

    per_approach_averages = {}
    for approach, cnt in approach_counts.items():
        if cnt <= 0:
            continue
        per_approach_averages[approach] = {
            "average_lines": float(approach_line_sum.get(approach, 0)) / cnt,
            "average_time": float(approach_time_sum.get(approach, 0.0)) / cnt,
            "count": cnt,
        }

    # Calculate implementation-specific averages (int vs bitvector)
    per_implementation_averages = {}
    for implementation, cnt in implementation_counts.items():
        if cnt <= 0:
            continue
        per_implementation_averages[implementation] = {
            "average_lines": float(implementation_line_sum.get(implementation, 0))
            / cnt,
            "average_time": float(implementation_time_sum.get(implementation, 0.0))
            / cnt,
            "count": cnt,
        }

    avg_lines_sorted = sorted(
        [
            {"approach": a, "average_lines": v["average_lines"]}
            for a, v in per_approach_averages.items()
        ],
        key=lambda x: (x["average_lines"], x["approach"]),
    )
    avg_time_sorted = sorted(
        [
            {"approach": a, "average_time": v["average_time"]}
            for a, v in per_approach_averages.items()
        ],
        key=lambda x: (x["average_time"], x["approach"]),
    )

    # Implementation-specific sorted lists (int vs bitvector comparison)
    implementation_avg_lines_sorted = sorted(
        [
            {"implementation": impl, "average_lines": v["average_lines"]}
            for impl, v in per_implementation_averages.items()
        ],
        key=lambda x: (x["average_lines"], x["implementation"]),
    )
    implementation_avg_time_sorted = sorted(
        [
            {"implementation": impl, "average_time": v["average_time"]}
            for impl, v in per_implementation_averages.items()
        ],
        key=lambda x: (x["average_time"], x["implementation"]),
    )

    constraints_avg_lines_sorted = sorted(
        [
            {"constraint_id": cid, "avg_lines": m["avg_lines"]}
            for cid, m in per_constraint_metrics.items()
        ],
        key=lambda x: (x["avg_lines"], x["constraint_id"]),
    )
    constraints_avg_time_sorted = sorted(
        [
            {"constraint_id": cid, "avg_time": m["avg_time"]}
            for cid, m in per_constraint_metrics.items()
        ],
        key=lambda x: (x["avg_time"], x["constraint_id"]),
    )

    return {
        "results_dir": str(results_dir),
        "constraints_checked": len(summaries),
        "counts_by_approach": counts_by_approach,
        "by_constraint": summaries,
        "metrics": {
            "per_constraint": per_constraint_metrics,
            "per_approach_averages": per_approach_averages,
            "per_implementation_averages": per_implementation_averages,  # New: int vs bitvector comparison
            "per_approach_sorted": {
                "avg_lines_sorted": avg_lines_sorted,
                "avg_time_sorted": avg_time_sorted,
            },
            "per_implementation_sorted": {  # New: int vs bitvector sorted lists
                "avg_lines_sorted": implementation_avg_lines_sorted,
                "avg_time_sorted": implementation_avg_time_sorted,
            },
            "constraints_sorted_by_avg": {
                "avg_lines_sorted": constraints_avg_lines_sorted,
                "avg_time_sorted": constraints_avg_time_sorted,
            },
        },
    }


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
        default=60000,
        help="Timeout in milliseconds (default: 60000 = 60 seconds)",
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

    args = parser.parse_args()

    if not os.path.exists(args.constraints_file):
        print(f"Error: Constraints file {args.constraints_file} not found")
        return

    # Determine if analysis should run
    run_analysis = args.analysis and not args.no_analysis

    print(f"Running constraint tests...")
    print(f"Analysis: {'Enabled' if run_analysis else 'Disabled'}")

    # Run constraint execution
    all_results = run_constraints_file(args.constraints_file, args.output_dir, args.timeout)

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
