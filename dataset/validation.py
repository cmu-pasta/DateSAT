"""
Enumeration baseline validation for integration test results.

This module validates symbolic solver results using the enumeration baseline implementation
instead of rebuilding constraints and checking them with Z3.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path so `import datesmt` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datesmt.enumeration_baseline import EnumerationSolver, EnumerationDateVar, ConstraintWrapper
from datesmt.constraint_parser import ConstraintParser
from datesmt.core import Date, Period

# --------------------------
# Parsing helpers
# --------------------------

DATE_RE = re.compile(r"^Date\((\-?\d{1,6}),\s*(\d{1,2}),\s*(\d{1,2})\)$")
PERIOD_RE = re.compile(r"^Period\((\-?\d+),\s*(\-?\d+),\s*(\-?\d+)\)$")


def parse_date_string(date_str: str) -> Date:
    """Parse a Date string into a Date object."""
    m = DATE_RE.match(date_str.strip())
    if not m:
        raise ValueError(f"Unrecognized Date format: {date_str}")
    year, month, day = map(int, m.groups())
    return Date(year, month, day)


def parse_period_string(period_str: str) -> Tuple[int, int, int]:
    """Parse a Period string into a tuple of (years, months, days)."""
    m = PERIOD_RE.match(period_str.strip())
    if not m:
        raise ValueError(f"Unrecognized Period format: {period_str}")
    y, mth, d = map(int, m.groups())
    return (y, mth, d)


# --------------------------
# Constraint execution helpers
# --------------------------


def _get_constraint_code(constraint_data: dict) -> str:
    """Get constraint code from new format constraint data."""
    parser = ConstraintParser()
    return parser.parse_constraint_data(constraint_data)


def execute_constraint_code(
    constraint_code: str, solution: Dict[str, str], constraint_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Execute constraint code with concrete values using Python-based enumeration solver.

    Args:
        constraint_code: The constraint code to execute
        solution: Dictionary mapping variable names to their concrete values
        constraint_data: Optional constraint data dict containing original constraint strings

    Returns:
        (is_satisfied, message, validated_constraints_str)
        validated_constraints_str: The original constraint strings that were validated (not SMT-LIB)
    """
    try:
        # For validation, we use EnumerationSolver which evaluates constraints in Python
        # We don't need SMT-LIB - we validate using Python date arithmetic
        enumeration_solver = EnumerationSolver()

        # Parse and create concrete variables with solution values
        for var_name, var_value in solution.items():
            var_value = var_value.strip()

            # Try to parse as Date
            try:
                date_obj = parse_date_string(var_value)
                enumeration_solver.add_date_var(
                    var_name, date_obj.year, date_obj.month, date_obj.day
                )
                continue
            except ValueError:
                pass

            # Try to parse as Period
            try:
                y, m, d = parse_period_string(var_value)
                # For concrete validation, we don't need to create period variables
                # since we removed PeriodVar support. We'll handle periods directly.
                continue
            except ValueError:
                pass

            return False, f"Could not parse variable {var_name} value: {var_value}", None

        # Re-execute the constraint code with enumeration solver and solution values
        # This will populate enumeration_solver.constraints with the constraints
        exec_globals_concrete = {
            'Date': Date,
            'Period': Period,
            'DateSMTBuilder': lambda: enumeration_solver,
            'result': enumeration_solver,
            'builder': enumeration_solver,
        }

        # Execute constraint code to build constraints with enumeration solver
        exec(constraint_code, exec_globals_concrete)

        # Get the original constraint strings that were validated (if available)
        validated_constraints_str = None
        if constraint_data and constraint_data.get("constraints"):
            # Save the original constraint strings that were validated
            validated_constraints_str = "\n".join(constraint_data.get("constraints", []))

        # Evaluate each constraint and check if all are satisfied
        # EnumerationSolver uses ConstraintWrapper objects for deferred evaluation
        failed_constraints = []
        solution_dict = {}
        for var_name, var_value in solution.items():
            var_value = var_value.strip()
            try:
                date_obj = parse_date_string(var_value)
                solution_dict[var_name] = Date(date_obj.year, date_obj.month, date_obj.day)
            except ValueError:
                pass

        # Use the validate_solution method which handles ConstraintWrapper evaluation
        if not enumeration_solver.validate_solution(solution_dict):
            # Get more details about which constraints failed
            for i, constraint in enumerate(enumeration_solver.constraints):
                try:
                    if isinstance(constraint, bool):
                        if not constraint:
                            failed_constraints.append(f"Constraint {i+1}: {constraint}")
                    elif isinstance(constraint, ConstraintWrapper):
                        if not constraint.evaluate():
                            failed_constraints.append(f"Constraint {i+1}: {constraint.description or 'constraint'}")
                    elif callable(constraint):
                        if not constraint():
                            failed_constraints.append(f"Constraint {i+1}: callable")
                    else:
                        try:
                            result = bool(constraint)
                            if not result:
                                failed_constraints.append(f"Constraint {i+1}: {constraint}")
                        except (TypeError, ValueError):
                            pass
                except Exception as e:
                    failed_constraints.append(f"Constraint {i+1}: Evaluation error - {str(e)}")

            if failed_constraints:
                return False, f"Solution does not satisfy constraints: {', '.join(failed_constraints)}", validated_constraints_str
            else:
                return False, "Solution does not satisfy constraints", validated_constraints_str

        return True, "Solution validated successfully with enumeration baseline", validated_constraints_str

    except Exception as e:
        return False, f"Error during constraint execution: {str(e)}", None


def validate_solution_with_concrete(
    constraint_data: dict,
    solution: Dict[str, Union[str, Date, Period]],
    constraint_id: str = "",
    save_dir: Optional[Path] = None,
    approach: str = "concrete",
) -> Tuple[bool, str, Optional[str]]:
    """
    Validate a solution using enumeration baseline (Python-based) implementation.

    This validates constraints using Python date arithmetic via EnumerationSolver,
    not SMT-LIB. The validation checks if the solution satisfies the constraints
    by evaluating them concretely in Python.

    Args:
        constraint_data: Constraint data dict in new format
        solution: Dictionary mapping variable names to their concrete values
                 (can be strings like "Date(2020, 3, 15)" or actual Date/Period objects)
        constraint_id: ID of the constraint
        save_dir: Optional directory to save validated constraint strings
        approach: Approach name (e.g., "hybrid_bitvector") for file naming

    Returns:
        (is_valid, message, validated_constraints_str)
        validated_constraints_str: The original constraint strings that were validated (not SMT-LIB)
    """
    if not solution:
        return False, "Empty solution", None

    # Convert new format to executable code
    constraint_code = _get_constraint_code(constraint_data)

    # Convert solution to string format if needed
    string_solution = {}
    for var_name, var_value in solution.items():
        if isinstance(var_value, str):
            string_solution[var_name] = var_value
        elif isinstance(var_value, Date):
            string_solution[var_name] = (
                f"Date({var_value.year}, {var_value.month}, {var_value.day})"
            )
        elif isinstance(var_value, Period):
            string_solution[var_name] = (
                f"Period({var_value.years}, {var_value.months}, {var_value.days})"
            )
        else:
            return False, f"Unknown variable type for {var_name}: {type(var_value)}", None

    # Execute the constraint with concrete values using Python-based enumeration solver
    # This validates using Python date arithmetic, not SMT-LIB
    success, message, validated_constraints_str = execute_constraint_code(
        constraint_code, string_solution, constraint_data
    )

    if not success:
        return False, f"Constraint execution failed: {message}", validated_constraints_str

    # Save the solution and constraints with substituted values
    # This shows what was actually validated using Python enumeration baseline implementation
    # Note: We save as .txt since these are constraint strings, not SMT-LIB
    # The folder name "smt2_assertion" is historical - these files contain constraint strings
    if save_dir is not None and validated_constraints_str:
        # Create a filename based on constraint_id and approach
        constraint_file = save_dir / f"{constraint_id}_{approach}_concrete_validation.txt"
        constraint_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with constraint_file.open("w", encoding="utf-8") as f:
                # Write header
                f.write("; Constraints validated through enumeration baseline (Python) validation\n")
                f.write("; Validation performed using Python date arithmetic (EnumerationSolver), not SMT-LIB\n\n")

                # Write the solution (variable assignments)
                f.write("; Solution:\n")
                for var_name, var_value in solution.items():
                    f.write(f"{var_name} = {var_value}\n")
                f.write("\n")

                # Write the original constraints
                f.write("; Original constraints:\n")
                for constraint in constraint_data.get("constraints", []):
                    f.write(f"{constraint}\n")
                f.write("\n")

                # Write constraints with solution substituted (what was actually evaluated)
                f.write("; Constraints with solution substituted (what was validated):\n")
                for constraint in constraint_data.get("constraints", []):
                    # Substitute each variable in the constraint with its solution value
                    substituted = constraint
                    for var_name, var_value in solution.items():
                        # Replace variable names with their values
                        # Simple substitution - replace 'x' with 'Date(2000, 2, 29)' etc.
                        # This is approximate but shows the concept
                        substituted = substituted.replace(var_name, var_value)
                    f.write(f"{substituted}\n")
        except Exception as e:
            # If we can't save the file, continue without it
            pass

    if success:
        return True, "Solution validated successfully with enumeration baseline", validated_constraints_str
    else:
        return False, message, validated_constraints_str


# --------------------------
# Results loading and grouping
# --------------------------


def load_results_files(results_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all result JSON files from a directory.

    Supports multiple file patterns:
    - results_*.json (legacy format)
    - *_*.json (e.g., baseline_int_20251105_013245.json from run_tests.py)

    Args:
        results_dir: Directory containing result JSON files

    Returns:
        List of all records from all result files
    """
    records: List[Dict[str, Any]] = []
    # Look for both old pattern (results_*.json) and new pattern (*_*.json)
    for pattern in ["results_*.json", "*_*.json"]:
        for path in sorted(results_dir.glob(pattern)):
            # Skip SMT2 files
            if path.suffix == '.smt2':
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records.extend(data)
            except (json.JSONDecodeError, IOError) as e:
                # Skip invalid files but don't fail
                print(f"Warning: Skipping invalid file {path}: {e}")
                continue
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


# --------------------------
# Batch validation
# --------------------------


def validate_sat_record(
    constraint_id: str, rec: Dict[str, Any], save_dir: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Validates the provided sat solution using enumeration baseline implementation.

    Returns:
      (is_valid, message)
    """
    approach = rec.get("approach")
    solution = rec.get("solution") or {}
    constraint_code = rec.get("constraint_code", "")

    if not isinstance(solution, dict) or not solution:
        return False, "missing or empty solution map"

    # Construct constraint data from new format fields for validation
    constraint_data = {
        "constraints": rec.get("constraints", []),
        "coverage_tags": rec.get("coverage_tags", []),
    }

    # Use concrete validation
    # Construct approach name from approach and implementation
    approach_name = f"{approach}_{rec.get('implementation', 'unknown')}"
    is_valid, message, smtlib_constraints = validate_solution_with_concrete(
        constraint_data, solution, constraint_id, save_dir, approach_name
    )

    return is_valid, message


def summarize_constraint(
    cid: str,
    approaches: Dict[str, Dict[str, Dict[str, Any]]],
    save_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Summarize validation results for a single constraint across all approaches.

    Uses enumeration baseline as ground truth for validation.

    Args:
        cid: Constraint ID
        approaches: Nested dict structure {approach: {implementation: record}}
        save_dir: Optional directory to save SMT-LIB constraints

    Returns:
        Dictionary with constraint summary including verdicts and validation results
    """
    # Flatten the nested structure for backward compatibility
    flattened_approaches: Dict[str, Dict[str, Any]] = {}
    for approach, implementations in approaches.items():
        for implementation, record in implementations.items():
            # Create a composite key for approach + implementation
            # For enumeration, implementation is "baseline"
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

    # Get enumeration baseline status (ground truth)
    enumeration_key = None
    for key in flattened_approaches.keys():
        if key.startswith("enumeration_"):
            enumeration_key = key
            break

    enumeration_status = approach_statuses.get(enumeration_key) if enumeration_key else None

    # For description, pick SAT one if any, else any
    any_rec = next(iter(sat_recs.values()), next(iter(flattened_approaches.values())))
    description = any_rec.get("description")

    # Validate SAT records using enumeration baseline
    sat_validation: Dict[str, Dict[str, Any]] = {}
    for a, r in sat_recs.items():
        ok, msg = validate_sat_record(cid, r, save_dir=save_dir)
        sat_validation[a] = {"valid": ok, "message": msg, "solution": r.get("solution")}

    # New validation logic based on enumeration baseline as ground truth
    per_approach_verdict: Dict[str, str] = {}

    # Check if all methods are SAT
    all_sat = len(approach_statuses) > 0 and all(
        s == "sat" for s in approach_statuses.values() if s != "timeout" and s != "error"
    )

    # Check if everything is UNSAT
    non_timeout_statuses = [s for s in approach_statuses.values() if s != "timeout" and s != "error"]
    all_unsat = len(non_timeout_statuses) > 0 and all(s == "unsat" for s in non_timeout_statuses)

    # Check if enumeration is SAT but others are UNSAT
    enumeration_sat_others_unsat = (
        enumeration_status == "sat" and
        all(s == "unsat" for k, s in approach_statuses.items()
            if k != enumeration_key and s != "timeout" and s != "error")
    )

    for a, status in approach_statuses.items():
        if status == "error":
            per_approach_verdict[a] = "error"
        elif status == "timeout":
            per_approach_verdict[a] = "timeout"
        elif status == "sat":
            # If all methods are SAT, validate using enumeration baseline
            if all_sat:
                vinfo = sat_validation.get(a)
                if vinfo and vinfo.get("valid"):
                    per_approach_verdict[a] = "correct"
                else:
                    per_approach_verdict[a] = "wrong"
            # If some are SAT, some are UNSAT, check if SAT ones are correct
            # If at least one SAT is correct, then UNSAT is wrong
            else:
                vinfo = sat_validation.get(a)
                if vinfo and vinfo.get("valid"):
                    per_approach_verdict[a] = "correct"
                else:
                    per_approach_verdict[a] = "wrong"
        elif status == "unsat":
            # If everything is UNSAT, then correct
            if all_unsat:
                per_approach_verdict[a] = "correct"
            # If enumeration is SAT but others are UNSAT, then UNSAT ones are wrong
            elif enumeration_sat_others_unsat:
                per_approach_verdict[a] = "wrong"
            # If some are SAT, some are UNSAT, check if at least one SAT is correct
            # If at least one SAT is correct, then UNSAT is wrong
            else:
                # Check if any SAT solution is valid
                any_valid_sat = any(
                    sat_validation.get(sat_key, {}).get("valid", False)
                    for sat_key in sat_recs.keys()
                )
                if any_valid_sat:
                    per_approach_verdict[a] = "wrong"
                else:
                    # No valid SAT solutions, UNSAT might be correct
                    per_approach_verdict[a] = "correct"
        else:
            per_approach_verdict[a] = "wrong"

    # Retain aggregate verdict fields for backward-compatibility
    any_error = any(s == "error" for s in approach_statuses.values())
    if any_error and not any(s == "sat" for s in approach_statuses.values()) and not all_unsat:
        verdict = "error"
        unsat_consensus = False
        wrong_approaches = [a for a, v in per_approach_verdict.items() if v == "wrong"]
        might_correct_approaches = []
    elif all_unsat:
        verdict = "correct_unsat"
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
        unsat_consensus = all_unsat
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
    """
    Comprehensive analysis of results directory with validation and metrics.

    This function generates the same format as run_tests.py's check_results_dir,
    including validation, verdicts, and metrics.

    Args:
        results_dir: Directory containing result JSON files

    Returns:
        Dictionary with comprehensive analysis results including:
        - Validation results with verdicts
        - Counts by approach (correct/wrong/error/timeout)
        - Metrics (SMT-LIB lines, execution times)
        - Per-constraint summaries
    """
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

                # Update approach-level metrics using composite key (approach_implementation)
                approach_line_sum[composite_key] = approach_line_sum.get(composite_key, 0) + lines
                approach_time_sum[composite_key] = approach_time_sum.get(composite_key, 0.0) + t
                approach_counts[composite_key] = approach_counts.get(composite_key, 0) + 1

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
            "per_implementation_averages": per_implementation_averages,
            "per_approach_sorted": {
                "avg_lines_sorted": avg_lines_sorted,
                "avg_time_sorted": avg_time_sorted,
            },
            "per_implementation_sorted": {
                "avg_lines_sorted": implementation_avg_lines_sorted,
                "avg_time_sorted": implementation_avg_time_sorted,
            },
            "constraints_sorted_by_avg": {
                "avg_lines_sorted": constraints_avg_lines_sorted,
                "avg_time_sorted": constraints_avg_time_sorted,
            },
        },
    }


def validate_results_with_concrete(results_dir: Path) -> Dict[str, Any]:
    """
    Validate all results in a directory using enumeration baseline implementation.

    Supports multiple result file patterns:
    - results_*.json (legacy format)
    - *_*.json (e.g., baseline_int_20251105_013245.json from run_tests.py)

    Args:
        results_dir: Directory containing result JSON files

    Returns:
        Dictionary with comprehensive validation results including:
        - Validation statistics
        - Per-constraint validation results with verdicts
        - Counts by approach (correct/wrong/error/timeout)
        - Approach statuses for all constraints
    """
    # Load all result files - support multiple patterns
    records = []
    # Look for both old pattern (results_*.json) and new pattern (*_*.json)
    for pattern in ["results_*.json", "*_*.json"]:
        for path in sorted(results_dir.glob(pattern)):
            # Skip SMT2 files
            if path.suffix == '.smt2':
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records.extend(data)
            except (json.JSONDecodeError, IOError) as e:
                # Skip invalid files but don't fail
                print(f"Warning: Skipping invalid file {path}: {e}")
                continue

    # Group by constraint ID, then by approach+implementation composite key
    # This handles cases where the same approach has multiple implementations (int, bitvector)
    grouped = {}
    for rec in records:
        cid = rec.get("constraint_id")
        approach = rec.get("approach")
        implementation = rec.get("implementation", "unknown")
        if not cid or not approach:
            continue
        # Create composite key to handle multiple implementations per approach
        approach_key = f"{approach}_{implementation}"
        grouped.setdefault(cid, {})[approach_key] = rec

    # Validate each constraint and compute verdicts
    validation_results = {}
    by_constraint = []
    counts_by_approach: Dict[str, Dict[str, int]] = {}

    for cid, approaches in sorted(grouped.items(), key=lambda kv: kv[0]):
        constraint_results = {}
        approach_statuses: Dict[str, str] = {}
        sat_validation: Dict[str, Dict[str, Any]] = {}
        verdicts_by_approach: Dict[str, str] = {}

        # Get description from first record
        first_record = next(iter(approaches.values()))
        description = first_record.get("description", "")

        for approach_key, record in approaches.items():
            status = record.get("status", "unknown")
            approach_statuses[approach_key] = status

            # Initialize counts for this approach
            if approach_key not in counts_by_approach:
                counts_by_approach[approach_key] = {
                    "correct": 0,
                    "wrong": 0,
                    "error": 0,
                    "timeout": 0,
                }

            # Handle different statuses
            if status == "sat":
                solution = record.get("solution", {})

                # Construct constraint data from record
                constraint_data = {
                    "constraints": record.get("constraints", []),
                    "coverage_tags": record.get("coverage_tags", []),
                }

                # Check if we have constraints to validate
                if not constraint_data.get("constraints"):
                    sat_validation[approach_key] = {
                        "valid": False,
                        "message": "No constraints available in record",
                        "solution": solution,
                    }
                    verdicts_by_approach[approach_key] = "wrong"
                    counts_by_approach[approach_key]["wrong"] += 1
                    continue

                # Validate using enumeration baseline implementation
                is_valid, message, _ = validate_solution_with_concrete(
                    constraint_data, solution, cid, None, approach_key
                )

                sat_validation[approach_key] = {
                    "valid": is_valid,
                    "message": message,
                    "solution": solution,
                }

                # Determine verdict: correct if valid, wrong if invalid
                if is_valid:
                    verdicts_by_approach[approach_key] = "correct"
                    counts_by_approach[approach_key]["correct"] += 1
                else:
                    verdicts_by_approach[approach_key] = "wrong"
                    counts_by_approach[approach_key]["wrong"] += 1

            elif status == "error":
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": f"Error status: {record.get('error_message', 'Unknown error')}",
                    "solution": record.get("solution", {}),
                }
                verdicts_by_approach[approach_key] = "error"
                counts_by_approach[approach_key]["error"] += 1
            elif status == "timeout":
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": "Solver timeout",
                    "solution": record.get("solution", {}),
                }
                verdicts_by_approach[approach_key] = "timeout"
                counts_by_approach[approach_key]["timeout"] += 1
            else:
                # UNSAT or other statuses
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": f"Status: {status}",
                    "solution": record.get("solution", {}),
                }
                # For UNSAT, we'd need to check consensus to determine correct/wrong
                # For now, mark as wrong (could be enhanced later)
                verdicts_by_approach[approach_key] = "wrong"
                counts_by_approach[approach_key]["wrong"] += 1

        # Store per-constraint summary
        by_constraint.append({
            "constraint_id": cid,
            "description": description,
            "approach_statuses": approach_statuses,
            "sat_validation": sat_validation,
            "verdicts_by_approach": verdicts_by_approach,
        })

        validation_results[cid] = constraint_results

    # Generate summary statistics
    total_constraints = len(validation_results)
    total_approaches = sum(
        len(approaches) for approaches in validation_results.values()
    )
    valid_approaches = sum(
        sum(1 for result in approaches.values() if result.get("valid", False))
        for approaches in validation_results.values()
    )

    total_correct = sum(
        counts.get("correct", 0) for counts in counts_by_approach.values()
    )

    return {
        "results_dir": str(results_dir),
        "validation_method": "concrete",
        "constraints_checked": total_constraints,
        "total_constraints": total_constraints,
        "total_approaches": total_approaches,
        "valid_approaches": valid_approaches,
        "validation_rate": (
            valid_approaches / total_approaches if total_approaches > 0 else 0
        ),
        "counts_by_approach": counts_by_approach,
        "constraint_results": validation_results,
        "by_constraint": by_constraint,
    }


def main():
    """Main function for concrete validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate integration test results using enumeration baseline implementation. "
                    "Supports results from run_tests.py (LLM constraints) and other datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate LLM constraint results
  python dataset/validation.py dataset/LLM_gen_constraints/results

  # Validate results from a specific dataset
  python dataset/validation.py dataset/law/results --output dataset/law/validation_results.json

  # Validate results that were run without analysis
  python dataset/validation.py dataset/LLM_gen_constraints/results --output validation_check.json
        """
    )
    parser.add_argument(
        "results_dir",
        nargs="?",
        default="results",
        help="Path to results directory containing result JSON files. "
             "Supports files matching patterns: results_*.json or *_*.json (e.g., baseline_int_*.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output filename (defaults to <results_dir>/concrete_validation.json)",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    if not results_dir.exists() or not results_dir.is_dir():
        raise SystemExit(f"Results directory not found: {results_dir}")

    # Use comprehensive analysis (same format as checked_summary.json)
    summary = check_results_dir(results_dir)

    output_path = (
        Path(args.output).resolve()
        if args.output
        else results_dir / "checked_summary.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=False)

    print(f"Validation and analysis completed:")
    print(f"  Constraints checked: {summary['constraints_checked']}")
    print(f"  Results saved to: {output_path}")

    # Print summary statistics
    counts = summary.get('counts_by_approach', {})
    if counts:
        print(f"\nSummary by approach:")
        for approach, counts_dict in counts.items():
            total = sum(counts_dict.values())
            correct = counts_dict.get('correct', 0)
            print(f"  {approach}: {correct}/{total} correct ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()
