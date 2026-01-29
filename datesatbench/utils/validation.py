"""
Concrete validation for integration test results.

This module validates symbolic solver results by executing constraints with concrete values
using Python date arithmetic. The enumeration baseline is used as ground truth for comparing
different approaches, but actual validation is performed by executing constraints directly
with concrete solutions rather than rebuilding constraints and checking them with Z3.
"""

import json
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path so `import datesat` works
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datesat.constraint_parser import ConstraintParser
from datesat.constraint_validator import validate_constraint_solution
from datesat.core import Date, Period
from datesat.enumeration_baseline import (
    ConstraintWrapper,
    EnumerationDateVar,
    EnumerationSolver,
)

# --------------------------
# Parsing helpers
# --------------------------

DATE_RE = re.compile(r"^Date\((\-?\d{1,6}),\s*(\d{1,2}),\s*(\d{1,2})\)$")
PERIOD_RE = re.compile(r"^Period\((\-?\d+),\s*(\-?\d+),\s*(\-?\d+)\)$")

ERROR_STATUS_VALUES = {"error", "parse_error", "validation_error", "builder_error"}


def normalize_status(status: Optional[str]) -> str:
    """Normalize status strings for downstream analysis."""
    if not status:
        return "unknown"
    status_lower = status.lower()
    if status_lower in ERROR_STATUS_VALUES:
        return "error"
    return status_lower


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
    constraint_code: str,
    solution: Dict[str, str],
    constraint_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Execute constraint code with concrete values using Python-based constraint validator.

    Args:
        constraint_code: The constraint code to execute
        solution: Dictionary mapping variable names to their concrete values
        constraint_data: Optional constraint data dict containing original constraint strings

    Returns:
        (is_satisfied, message, validated_constraints_str)
        validated_constraints_str: The original constraint strings that were validated (not SMT-LIB)
    """
    try:
        # Parse solution values into proper types (Date/int/bool) for the validator
        parsed_solution: Dict[str, Union[Date, int, bool]] = {}

        for var_name, var_value in solution.items():
            if isinstance(var_value, str):
                var_value = var_value.strip()

                # Try to parse as Date
                try:
                    date_obj = parse_date_string(var_value)
                    parsed_solution[var_name] = date_obj
                    continue
                except ValueError:
                    pass

                # Try to parse as Period (skip for now, periods not in solutions)
                try:
                    y, m, d = parse_period_string(var_value)
                    # For concrete validation, we don't need to store period values
                    continue
                except ValueError:
                    pass

                # Try bool
                lv = var_value.lower()
                if lv in ("true", "false", "1", "0", "yes", "no", "y", "n", "t", "f"):
                    parsed_solution[var_name] = lv in ("true", "1", "yes", "y", "t")
                    continue

                # Try int
                try:
                    parsed_solution[var_name] = int(var_value)
                    continue
                except ValueError:
                    pass

                return (
                    False,
                    f"Could not parse variable {var_name} value: {var_value}",
                    None,
                )
            else:
                # Already parsed (int/bool/Date)
                parsed_solution[var_name] = var_value

        # Build validated constraints string from original data (if present)
        validated_constraints_str = None
        if constraint_data and constraint_data.get("constraints"):
            constraint_strs = []
            for constraint_item in constraint_data.get("constraints", []):
                if isinstance(constraint_item, list):
                    constraint_strs.append("(" + " OR ".join(constraint_item) + ")")
                else:
                    constraint_strs.append(constraint_item)
            validated_constraints_str = "\n".join(constraint_strs)

        # Evaluate using the pure-Python constraint validator (supports date/bool/int)
        ok, msg = validate_constraint_solution(constraint_code, parsed_solution)
        if ok:
            # Preserve the message from validate_constraint_solution (may include warning info)
            return True, msg, validated_constraints_str
        return False, f"Constraint execution failed: {msg}", validated_constraints_str

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
    Validate a solution by executing constraints with concrete values.

    This validates constraints using Python date arithmetic via the constraint validator,
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
    try:
        constraint_code = _get_constraint_code(constraint_data)
    except ValueError as e:
        # Likely undeclared variables or unsupported constructs
        return False, f"Validation not supported: {e}", None

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
        elif isinstance(var_value, bool):
            string_solution[var_name] = "True" if var_value else "False"
        elif isinstance(var_value, int):
            string_solution[var_name] = str(var_value)
        else:
            return (
                False,
                f"Unknown variable type for {var_name}: {type(var_value)}",
                None,
            )

    # Execute the constraint with concrete values using Python-based enumeration solver.
    # This validates using Python date arithmetic, not SMT-LIB. The message from
    # validate_constraint_solution will include warning information if intermediate
    # dates went outside the allowed range, which upstream code will use to classify
    # cases as "warning_correct" or "warning_wrong" based on whether validation
    # actually succeeded.
    success, message, validated_constraints_str = execute_constraint_code(
        constraint_code, string_solution, constraint_data
    )

    if not success:
        # Validation actually failed - return False
        return (
            False,
            f"Constraint execution failed: {message}",
            validated_constraints_str,
        )

    # If evaluation succeeded, return True. The message already includes warning info
    # if present (from validate_constraint_solution). Upstream code will check both
    # success and warning status to determine "warning_correct" vs "warning_wrong".
    return (
        True,
        message,  # Preserve message which may include warning info
        validated_constraints_str,
    )

    # Save the solution and constraints with substituted values
    # This shows what was actually validated using Python constraint validator
    # Note: We save as .txt since these are constraint strings, not SMT-LIB
    # The folder name "smt2_assertion" is historical - these files contain constraint strings
    if save_dir is not None and validated_constraints_str:
        # Create a filename based on constraint_id and approach
        constraint_file = (
            save_dir / f"{constraint_id}_{approach}_concrete_validation.txt"
        )
        constraint_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with constraint_file.open("w", encoding="utf-8") as f:
                # Write header
                f.write(
                    "; Constraints validated through concrete (Python) validation\n"
                )
                f.write(
                    "; Validation performed using Python date arithmetic (constraint validator), not SMT-LIB\n\n"
                )

                # Write the solution (variable assignments)
                f.write("; Solution:\n")
                for var_name, var_value in solution.items():
                    f.write(f"{var_name} = {var_value}\n")
                f.write("\n")

                # Write the original constraints
                f.write("; Original constraints:\n")
                for constraint_item in constraint_data.get("constraints", []):
                    if isinstance(constraint_item, list):
                        # OR clause: format as (c1 OR c2 OR ...)
                        f.write(f";   ({' OR '.join(constraint_item)})\n")
                    else:
                        f.write(f";   {constraint_item}\n")
                f.write("\n")

                # Write constraints with solution substituted (what was actually evaluated)
                f.write(
                    "; Constraints with solution substituted (what was validated):\n"
                )
                for constraint_item in constraint_data.get("constraints", []):
                    # Handle CNF format
                    if isinstance(constraint_item, list):
                        # OR clause: format as (c1 OR c2 OR ...)
                        constraint = f"({' OR '.join(constraint_item)})"
                    else:
                        constraint = constraint_item
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
        return (
            True,
            "Solution validated successfully with concrete validation",
            validated_constraints_str,
        )
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
            if path.suffix == ".smt2":
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
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]:
    """
    Groups records by constraint_id, then by approach, then by implementation.
    Structure: {constraint_id: {approach: {implementation: record}}}
    """
    grouped: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
    for rec in records:
        cid = rec.get("id")
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
    Validates the provided SAT solution by executing constraints with concrete values.

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
        "declarations": rec.get("declarations", []),
        "coverage_tags": rec.get("coverage_tags", []),
    }

    # Use concrete validation (execute constraints with concrete values)
    # Construct approach name from approach and implementation
    approach_name = f"{approach}_{rec.get('implementation', 'unknown')}"
    is_valid, message, _ = validate_solution_with_concrete(
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

    Uses enumeration baseline results as ground truth for comparing approaches.
    Validates SAT solutions by executing constraints with concrete values.

    Args:
        cid: Constraint ID
        approaches: Nested dict structure {approach: {implementation: record}}
        save_dir: Optional directory to save constraint validation files

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
    normalized_statuses: Dict[str, str] = {
        a: normalize_status(status) for a, status in approach_statuses.items()
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

    enumeration_status = (
        normalized_statuses.get(enumeration_key) if enumeration_key else None
    )

    # If enumeration is not_applicable, treat it like timeout for comparison purposes
    # but we'll still categorize the constraint as not supported
    enumeration_available = enumeration_status not in ("not_applicable", None)

    # Validate SAT records by executing constraints with concrete values
    sat_validation: Dict[str, Dict[str, Any]] = {}
    # Always validate SAT records using the Python constraint validator
    # (validation does not depend on enumeration baseline availability).
    for a, r in sat_recs.items():
        ok, msg = validate_sat_record(cid, r, save_dir=save_dir)
        sat_validation[a] = {"valid": ok, "message": msg, "solution": r.get("solution")}

    # Determine per-approach verdicts using enumeration baseline results as ground truth
    per_approach_verdict: Dict[str, str] = {}

    # Check if all methods are SAT (excluding timeout, error, and not_applicable)
    all_sat = len(normalized_statuses) > 0 and all(
        s == "sat"
        for s in normalized_statuses.values()
        if s not in ("timeout", "error", "not_applicable")
    )

    # Check if everything is UNSAT (excluding timeout, error, and not_applicable)
    non_timeout_statuses = [
        s
        for s in normalized_statuses.values()
        if s not in ("timeout", "error", "not_applicable")
    ]
    all_unsat = len(non_timeout_statuses) > 0 and all(
        s == "unsat" for s in non_timeout_statuses
    )

    # Check if enumeration is SAT but others are UNSAT
    # Treat UNSAT approaches as wrong only if there exists at least one SAT approach
    # whose solution validates correctly. Specifically, the special case where
    # enumeration is SAT and all others are UNSAT should only penalize the UNSAT
    # approaches when enumeration's SAT solution is valid.
    # Skip this check if enumeration is not_applicable
    enum_vinfo = sat_validation.get(enumeration_key) if enumeration_available else None
    enum_valid = bool(enum_vinfo and enum_vinfo.get("valid"))
    enumeration_sat_others_unsat = (
        enumeration_available
        and enumeration_status == "sat"
        and enum_valid
        and all(
            s == "unsat"
            for k, s in normalized_statuses.items()
            if k != enumeration_key and s not in ("timeout", "error", "not_applicable")
        )
    )

    for a, status in normalized_statuses.items():
        # Process each approach based on its own status
        if status == "error":
            per_approach_verdict[a] = "error"
        elif status == "timeout":
            per_approach_verdict[a] = "timeout"
        elif status == "not_applicable":
            # This approach (e.g., enumeration) is not_applicable
            # Treat like timeout - don't penalize, but don't count as correct either
            per_approach_verdict[a] = "not_applicable"
        elif status == "sat":
            # All SAT records were validated, so sat_validation[a] must exist
            vinfo = sat_validation[a]
            msg = vinfo["message"]
            has_warning = isinstance(msg, str) and "Date outside allowed range" in msg
            if vinfo["valid"] is True:
                if has_warning:
                    per_approach_verdict[a] = "warning_correct"
                else:
                    per_approach_verdict[a] = "correct"
            elif vinfo["valid"] is False:
                if has_warning:
                    per_approach_verdict[a] = "warning_wrong"
                else:
                    per_approach_verdict[a] = "wrong"
            else:
                # Fallback to status-based heuristics
                if not enumeration_available:
                    other_statuses = [
                        s
                        for k, s in normalized_statuses.items()
                        if k != enumeration_key
                        and k != a
                        and s not in ("timeout", "error", "not_applicable")
                    ]
                    if not other_statuses or all(s == "sat" for s in other_statuses):
                        per_approach_verdict[a] = "correct"
                    elif all(s == "unsat" for s in other_statuses):
                        per_approach_verdict[a] = "wrong"
                    else:
                        per_approach_verdict[a] = "correct"
                elif all_sat:
                    per_approach_verdict[a] = "wrong"
                else:
                    per_approach_verdict[a] = "wrong"
        elif status == "unsat":
            # If enumeration is not_applicable, compare other approaches against each other
            if not enumeration_available:
                # Compare this approach against other non-enumeration approaches
                other_statuses = [
                    s
                    for k, s in normalized_statuses.items()
                    if k != enumeration_key
                    and k != a
                    and s not in ("timeout", "error", "not_applicable")
                ]
                if not other_statuses:
                    # Only this approach, can't compare
                    per_approach_verdict[a] = "correct"
                elif all(s == "unsat" for s in other_statuses):
                    # All other approaches also UNSAT, mark as correct (they agree)
                    per_approach_verdict[a] = "correct"
                elif any(s == "sat" for s in other_statuses):
                    # Some others are SAT - check if any SAT solution is valid
                    # UNSAT is only wrong if at least one SAT solution is valid
                    # All SAT records were validated, so sat_validation[key] must exist
                    any_valid_sat = any(
                        sat_validation[sat_key]["valid"]
                        for sat_key in sat_recs.keys()
                        if normalized_statuses.get(sat_key) != "not_applicable"
                    )
                    if any_valid_sat:
                        per_approach_verdict[a] = "wrong"
                    else:
                        # No valid SAT solutions, UNSAT is correct
                        per_approach_verdict[a] = "correct"
                else:
                    # Mixed results - can't determine, mark as correct (conservative)
                    per_approach_verdict[a] = "correct"
            # If everything is UNSAT, then correct
            elif all_unsat:
                per_approach_verdict[a] = "correct"
            # If enumeration is SAT but others are UNSAT, then UNSAT ones are wrong
            elif enumeration_sat_others_unsat:
                per_approach_verdict[a] = "wrong"
            # If some are SAT, some are UNSAT, check if at least one SAT is correct
            # If at least one SAT is correct, then UNSAT is wrong
            else:
                # Check if any SAT solution is valid (excluding enumeration if it's not_applicable)
                # All SAT records were validated, so sat_validation[key] must exist
                any_valid_sat = any(
                    sat_validation[sat_key]["valid"]
                    for sat_key in sat_recs.keys()
                    if normalized_statuses.get(sat_key) != "not_applicable"
                )
                if any_valid_sat:
                    per_approach_verdict[a] = "wrong"
                else:
                    # No valid SAT solutions, UNSAT might be correct
                    per_approach_verdict[a] = "correct"
        else:
            per_approach_verdict[a] = "wrong"

    # Retain aggregate verdict fields for backward-compatibility
    any_error = any(s == "error" for s in normalized_statuses.values())
    if (
        any_error
        and not any(s == "sat" for s in approach_statuses.values())
        and not all_unsat
    ):
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
        # Exclude "not_applicable" and "timeout" from the "all correct" check
        applicable_verdicts = [
            v
            for v in per_approach_verdict.values()
            if v not in ("not_applicable", "timeout")
        ]
        if applicable_verdicts and all(
            v in ("correct", "warning_correct") for v in applicable_verdicts
        ):
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
        "approach_statuses": approach_statuses,
        "sat_validation": sat_validation,  # per-sat approach validity and messages
        "unsat_consensus": unsat_consensus,
        "verdicts_by_approach": per_approach_verdict,  # per-approach: "correct" | "wrong" | "error"
        "wrong_approaches": wrong_approaches,
        "might_correct_approaches": might_correct_approaches,
    }


def check_results_dir(
    results_dir: Path, enumeration_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Comprehensive analysis of results directory with validation and metrics.

    This function generates the same format as run_tests.py's check_results_dir,
    including validation, verdicts, and metrics.

    Args:
        results_dir: Directory containing result JSON files
        enumeration_filter: If "supported", only include constraints where the
            enumeration baseline is applicable. If "not_supported", only include
            constraints where enumeration baseline reports not_applicable. If
            None (default), include all constraints.

    Returns:
        Dictionary with comprehensive analysis results including:
        - Validation results with verdicts
        - Counts by approach (correct/wrong/error/timeout)
        - Metrics (SMT-LIB lines, execution times)
        - Per-constraint summaries
    """
    if enumeration_filter not in (None, "supported", "not_supported"):
        raise ValueError(
            "enumeration_filter must be one of None, 'supported', or 'not_supported'"
        )

    records = load_results_files(results_dir)
    grouped = group_by_constraint(records)

    summaries: List[Dict[str, Any]] = []
    counts_by_approach: Dict[str, Dict[str, int]] = {}
    save_dir = results_dir / "smt2_assertion"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Build summaries for every constraint first so we can filter later
    for cid, approaches in sorted(grouped.items(), key=lambda kv: kv[0]):
        summary = summarize_constraint(cid, approaches, save_dir=save_dir)
        summaries.append(summary)

    # Categorize constraints by enumeration baseline support
    enumeration_supported_constraints: List[str] = []
    enumeration_not_supported_constraints: List[str] = []

    for summary in summaries:
        cid = summary.get("constraint_id")
        verdicts = summary.get("verdicts_by_approach", {})

        enumeration_not_applicable = any(
            approach_key.startswith("enumeration_") and verdict == "not_applicable"
            for approach_key, verdict in verdicts.items()
        )

        if enumeration_not_applicable:
            enumeration_not_supported_constraints.append(cid)
        else:
            enumeration_supported_constraints.append(cid)

    # Decide which constraints to keep based on enumeration_filter
    if enumeration_filter == "supported":
        included_constraint_ids = set(enumeration_supported_constraints)
        filter_mode = "supported"
    elif enumeration_filter == "not_supported":
        included_constraint_ids = set(enumeration_not_supported_constraints)
        filter_mode = "not_supported"
    else:
        included_constraint_ids = {s.get("constraint_id") for s in summaries}
        filter_mode = "all"

    filtered_summaries = [
        s for s in summaries if s.get("constraint_id") in included_constraint_ids
    ]

    # If we're focusing on constraints where enumeration is not supported,
    # drop enumeration_* approach details from the per-constraint summaries so we
    # don't emit stats for not_applicable enumeration runs.
    if filter_mode == "not_supported":
        cleaned_summaries: List[Dict[str, Any]] = []
        for summary in filtered_summaries:
            cleaned = dict(summary)
            # Strip enumeration_* entries from nested maps
            for key in ("approach_statuses", "sat_validation", "verdicts_by_approach"):
                if key in cleaned and isinstance(cleaned[key], dict):
                    cleaned[key] = {
                        k: v
                        for k, v in cleaned[key].items()
                        if not k.startswith("enumeration_")
                    }
            # Remove enumeration entries from wrong_approaches / might_correct_approaches
            for key in ("wrong_approaches", "might_correct_approaches"):
                if key in cleaned and isinstance(cleaned[key], list):
                    cleaned[key] = [
                        k for k in cleaned[key] if not str(k).startswith("enumeration_")
                    ]
            cleaned_summaries.append(cleaned)
        filtered_summaries = cleaned_summaries

    # Recompute counts using the filtered subset
    for summary in filtered_summaries:
        per = summary.get("verdicts_by_approach", {})
        for approach, v in per.items():
            if approach not in counts_by_approach:
                counts_by_approach[approach] = {
                    "correct": 0,
                    "wrong": 0,
                    "error": 0,
                    "timeout": 0,
                    "warning_correct": 0,
                    "warning_wrong": 0,
                    "not_applicable": 0,
                }
            # Only track not_applicable for enumeration_* approaches; DateSAT methods
            # shouldn't produce this status.
            if v == "not_applicable" and not approach.startswith("enumeration_"):
                continue
            if v in counts_by_approach[approach]:
                counts_by_approach[approach][v] += 1

    # For the not_supported view, strip the not_applicable bucket from
    # non-enumeration approaches entirely so it doesn't appear in output.
    if filter_mode == "not_supported":
        for approach in list(counts_by_approach.keys()):
            if not approach.startswith("enumeration_"):
                counts_by_approach[approach].pop("not_applicable", None)

    # --------------------------
    # Metrics: SMT-LIB file size (lines) and execution time
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
        if cid not in included_constraint_ids:
            continue

        entries = []
        for approach, implementations in appr_map.items():
            # For the not_supported view, skip enumeration_* approaches entirely
            if filter_mode == "not_supported" and approach.startswith("enumeration_"):
                continue
            for implementation, rec in implementations.items():
                smt_path = rec.get("smtlib_file")
                lines = _smt2_lines(smt_path)
                t = float(rec.get("execution_time") or 0.0)

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

                approach_line_sum[composite_key] = (
                    approach_line_sum.get(composite_key, 0) + lines
                )
                approach_time_sum[composite_key] = (
                    approach_time_sum.get(composite_key, 0.0) + t
                )
                approach_counts[composite_key] = (
                    approach_counts.get(composite_key, 0) + 1
                )

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
        "constraints_checked": len(filtered_summaries),
        "counts_by_approach": counts_by_approach,
        "by_constraint": filtered_summaries,
        "enumeration_filter": filter_mode,
        "enumeration_support": {
            "supported": enumeration_supported_constraints,
            "not_supported": enumeration_not_supported_constraints,
            "supported_count": len(enumeration_supported_constraints),
            "not_supported_count": len(enumeration_not_supported_constraints),
        },
        "metrics": {
            # "per_constraint": per_constraint_metrics,
            # "per_approach_averages": per_approach_averages,
            # "per_implementation_averages": per_implementation_averages,
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
    Validate all results in a directory by executing constraints with concrete values.

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
            if path.suffix == ".smt2":
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
        normalized_statuses: Dict[str, str] = {}

        # First pass: validate all SAT solutions
        for approach_key, record in approaches.items():
            status = record.get("status", "unknown")
            normalized_status = normalize_status(status)
            approach_statuses[approach_key] = status
            normalized_statuses[approach_key] = normalized_status

            # Initialize counts for this approach
            if approach_key not in counts_by_approach:
                counts_by_approach[approach_key] = {
                    "correct": 0,
                    "wrong": 0,
                    "error": 0,
                    "timeout": 0,
                    "warning_correct": 0,
                    "warning_wrong": 0,
                }

            # Handle SAT statuses - validate solutions
            if normalized_status == "sat":
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
                    continue

                # Validate by executing constraints with concrete values
                is_valid, message, _ = validate_solution_with_concrete(
                    constraint_data, solution, cid, None, approach_key
                )

                sat_validation[approach_key] = {
                    "valid": is_valid,
                    "message": message,
                    "solution": solution,
                }

        # Second pass: assign verdicts based on status and SAT validation results
        # Check if any SAT solution is valid
        # All SAT approaches were validated in first pass, so sat_validation[key] must exist
        any_valid_sat = any(
            sat_validation[approach_key]["valid"]
            for approach_key in approaches.keys()
            if normalized_statuses.get(approach_key) == "sat"
        )

        for approach_key, record in approaches.items():
            normalized_status = normalized_statuses[approach_key]

            if normalized_status == "sat":
                # Determine verdict: correct if valid, wrong if invalid
                # All SAT approaches were validated in first pass, so sat_validation[key] must exist
                vinfo = sat_validation[approach_key]
                message = vinfo["message"]
                has_warning = isinstance(message, str) and "Date outside allowed range" in message
                if vinfo["valid"] is True:
                    if has_warning:
                        verdicts_by_approach[approach_key] = "warning_correct"
                        counts_by_approach[approach_key]["warning_correct"] += 1
                    else:
                        verdicts_by_approach[approach_key] = "correct"
                        counts_by_approach[approach_key]["correct"] += 1
                else:
                    if has_warning:
                        verdicts_by_approach[approach_key] = "warning_wrong"
                        counts_by_approach[approach_key]["warning_wrong"] += 1
                    else:
                        verdicts_by_approach[approach_key] = "wrong"
                        counts_by_approach[approach_key]["wrong"] += 1

            elif normalized_status == "error":
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": f"Error status: {record.get('error_message', 'Unknown error')}",
                    "solution": record.get("solution", {}),
                }
                verdicts_by_approach[approach_key] = "error"
                counts_by_approach[approach_key]["error"] += 1
            elif normalized_status == "timeout":
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": "Solver timeout",
                    "solution": record.get("solution", {}),
                }
                verdicts_by_approach[approach_key] = "timeout"
                counts_by_approach[approach_key]["timeout"] += 1
            elif normalized_status == "unsat":
                # UNSAT is only wrong if there exists at least one valid SAT solution
                # If all SAT solutions are invalid, then UNSAT is correct
                constraint_results[approach_key] = {
                    "valid": not any_valid_sat,
                    "message": f"Status: unsat (valid={not any_valid_sat} based on SAT validation)",
                    "solution": record.get("solution", {}),
                }
                if any_valid_sat:
                    # At least one SAT solution is valid, so UNSAT is wrong
                    verdicts_by_approach[approach_key] = "wrong"
                    counts_by_approach[approach_key]["wrong"] += 1
                else:
                    # No valid SAT solutions, UNSAT is correct
                    verdicts_by_approach[approach_key] = "correct"
                    counts_by_approach[approach_key]["correct"] += 1
            else:
                # Unknown or other statuses
                constraint_results[approach_key] = {
                    "valid": False,
                    "message": f"Status: {normalized_status}",
                    "solution": record.get("solution", {}),
                }
                verdicts_by_approach[approach_key] = "wrong"
                counts_by_approach[approach_key]["wrong"] += 1

        # Store per-constraint summary
        by_constraint.append(
            {
                "constraint_id": cid,
                "approach_statuses": approach_statuses,
                "sat_validation": sat_validation,
                "verdicts_by_approach": verdicts_by_approach,
            }
        )

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
        description="Validate integration test results by executing constraints with concrete values. "
        "Supports results from run_tests.py (LLM constraints) and other datesatbenchs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate LLM constraint results
  python datesatbench/utils/validation.py datesatbench/LLM_gen_constraints/results

  # Validate results from a specific datesatbench
  python datesatbench/utils/validation.py datesatbench/law/results --output datesatbench/law/validation_results.json

  # Validate results that were run without analysis
  python datesatbench/utils/validation.py datesatbench/LLM_gen_constraints/results --output validation_check.json
        """,
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
    counts = summary.get("counts_by_approach", {})
    if counts:
        print(f"\nSummary by approach:")
        for approach, counts_dict in counts.items():
            total = sum(counts_dict.values())
            correct = counts_dict.get("correct", 0)
            print(f"  {approach}: {correct}/{total} correct ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()
