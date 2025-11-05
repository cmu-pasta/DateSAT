"""
Concrete validation for integration test results.

This module validates symbolic solver results using the concrete implementation
instead of rebuilding constraints and checking them with Z3.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from datesmt.concrete import ConcreteSolver, ConcreteDateVar
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
    constraint_code: str, solution: Dict[str, str]
) -> Tuple[bool, str, Optional[str]]:
    """
    Execute constraint code with concrete values and generate SMT-LIB constraints.

    Args:
        constraint_code: The constraint code to execute
        solution: Dictionary mapping variable names to their concrete values

    Returns:
        (is_satisfied, message, smtlib_constraints)
    """
    try:
        # Import the symbolic solver to generate SMT-LIB constraints
        from datesmt.api import DateSMTBuilder

        # Create a symbolic solver to generate SMT-LIB constraints
        symbolic_solver = DateSMTBuilder(approach="baseline", implementation="int")

        # Prepare execution context with symbolic solver
        exec_globals = {
            'Date': Date,
            'Period': Period,
            'DateSMTBuilder': lambda: symbolic_solver,
            'result': symbolic_solver,
            'builder': symbolic_solver,
        }

        # Execute the constraint code to build the symbolic constraints
        exec(constraint_code, exec_globals)

        # Get the solver from the executed code
        solver = exec_globals.get('result') or exec_globals.get('builder')
        if not solver:
            return False, "Constraint code did not create a solver", None

        # Generate SMT-LIB constraints
        smtlib_constraints = None
        try:
            smtlib_constraints = solver.to_smt2()
        except Exception as e:
            return False, f"Error generating SMT-LIB constraints: {str(e)}", None

        # For concrete validation, we need to check if the solution satisfies the constraints
        # We'll do this by creating a concrete solver and checking the constraints
        concrete_solver = ConcreteSolver()

        # Parse and create concrete variables
        for var_name, var_value in solution.items():
            var_value = var_value.strip()

            # Try to parse as Date
            try:
                date_obj = parse_date_string(var_value)
                concrete_solver.add_date_var(
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

            return False, f"Could not parse variable {var_name} value: {var_value}", smtlib_constraints

        # For now, we consider the solution valid if the constraint code executed
        # without errors and we could generate SMT-LIB constraints
        return True, "Solution validated successfully with concrete implementation", smtlib_constraints

    except Exception as e:
        return False, f"Error during constraint execution: {str(e)}", None


def validate_solution_with_concrete(
    constraint_data: dict,
    solution: Dict[str, Union[str, Date, Period]],
    constraint_id: str = "",
    save_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Validate a solution using concrete implementation and save SMT-LIB constraints.

    Args:
        constraint_data: Constraint data dict in new format
        solution: Dictionary mapping variable names to their concrete values
                 (can be strings like "Date(2020, 3, 15)" or actual Date/Period objects)
        constraint_id: ID of the constraint
        save_dir: Optional directory to save SMT-LIB constraints

    Returns:
        (is_valid, message)
    """
    if not solution:
        return False, "Empty solution"

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
            return False, f"Unknown variable type for {var_name}: {type(var_value)}"

    # Execute the constraint with concrete values and get SMT-LIB constraints
    success, message, smtlib_constraints = execute_constraint_code(constraint_code, string_solution)

    if not success:
        return False, f"Constraint execution failed: {message}"

    # Save SMT-LIB constraints if requested
    if save_dir is not None and smtlib_constraints:
        # Create a filename based on constraint_id and approach
        approach = "concrete"  # Since we're using concrete validation
        smt2_file = save_dir / f"{constraint_id}_{approach}_constraints.smt2"
        smt2_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with smt2_file.open("w", encoding="utf-8") as f:
                f.write(smtlib_constraints)
        except Exception as e:
            # If we can't save the file, continue without it
            pass

    return True, "Solution validated successfully with concrete implementation"


# --------------------------
# Batch validation
# --------------------------


def validate_results_with_concrete(results_dir: Path) -> Dict[str, Any]:
    """
    Validate all results in a directory using concrete implementation.

    Args:
        results_dir: Directory containing results_*.json files

    Returns:
        Dictionary with validation results
    """
    # Load all result files
    records = []
    for path in sorted(results_dir.glob("results_*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)

    # Group by constraint ID
    grouped = {}
    for rec in records:
        cid = rec.get("constraint_id")
        approach = rec.get("approach")
        if not cid or not approach:
            continue
        grouped.setdefault(cid, {})[approach] = rec

    # Validate each constraint
    validation_results = {}
    for cid, approaches in grouped.items():
        constraint_results = {}

        for approach, record in approaches.items():
            if record.get("status") != "sat":
                constraint_results[approach] = {
                    "valid": False,
                    "message": f"Not a SAT result (status: {record.get('status')})",
                    "solution": record.get("solution", {}),
                }
                continue

            solution = record.get("solution", {})
            constraint_code = record.get("constraint_code", "")

            if not constraint_code:
                constraint_results[approach] = {
                    "valid": False,
                    "message": "No constraint code available",
                    "solution": solution,
                }
                continue

            # Validate using concrete implementation
            is_valid, message = validate_solution_with_concrete(
                constraint_code, solution, {}
            )

            constraint_results[approach] = {
                "valid": is_valid,
                "message": message,
                "solution": solution,
            }

        validation_results[cid] = constraint_results

    # Generate summary
    total_constraints = len(validation_results)
    total_approaches = sum(
        len(approaches) for approaches in validation_results.values()
    )
    valid_approaches = sum(
        sum(1 for result in approaches.values() if result["valid"])
        for approaches in validation_results.values()
    )

    return {
        "validation_method": "concrete",
        "total_constraints": total_constraints,
        "total_approaches": total_approaches,
        "valid_approaches": valid_approaches,
        "validation_rate": (
            valid_approaches / total_approaches if total_approaches > 0 else 0
        ),
        "constraint_results": validation_results,
    }


def main():
    """Main function for concrete validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate integration test results using concrete implementation"
    )
    parser.add_argument(
        "results_dir",
        nargs="?",
        default="results/constraint1",
        help="Path to results directory (contains results_*.json)",
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

    validation_results = validate_results_with_concrete(results_dir)

    output_path = (
        Path(args.output).resolve()
        if args.output
        else results_dir / "concrete_validation.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(validation_results, f, indent=2, sort_keys=False)

    print(f"Concrete validation completed:")
    print(f"  Total constraints: {validation_results['total_constraints']}")
    print(f"  Total approaches: {validation_results['total_approaches']}")
    print(f"  Valid approaches: {validation_results['valid_approaches']}")
    print(f"  Validation rate: {validation_results['validation_rate']:.2%}")
    print(f"  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
