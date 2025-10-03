"""
Enhanced template file to test generated constraints with both baseline and advanced approaches.
Now supports the enhanced schema with coverage tags and expected satisfiability.
"""

import json
import os
import sys
import time
from datetime import datetime

# Add datesmt to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'datesmt'))

try:
    from datesmt.core import Date, Period
    from datesmt.symbolic_api import DateSMTBuilder
except ImportError:
    # Fallback for when running from different directory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from datesmt.core import Date, Period
    from datesmt.symbolic_api import DateSMTBuilder


def test_constraint_with_approach(constraint_data: dict, approach: str, timeout_ms: int = 60000) -> dict:
    """Test a single constraint with a specific approach."""

    constraint_id = constraint_data["id"]
    constraint_code = constraint_data["constraint_code"]
    description = constraint_data.get("description", "")
    variables = constraint_data.get("variables", [])
    coverage_tags = constraint_data.get("coverage_tags", [])
    expected_satisfiable = constraint_data.get("expected_satisfiable", True)

    print(f"\n=== Testing {constraint_id} ({approach.upper()}) ===")
    print(f"Description: {description}")
    print(f"Coverage tags: {', '.join(coverage_tags)}")
    print(f"Expected satisfiable: {expected_satisfiable}")
    print(f"Constraint: {constraint_code}")

    result = {
        "constraint_id": constraint_id,
        "description": description,
        "constraint_code": constraint_code,
        "variables": variables,
        "coverage_tags": coverage_tags,
        "expected_satisfiable": expected_satisfiable,
        "approach": approach,
        "status": "error",
        "execution_time": 0,
        "error_message": None,
        "solution": None,
        "prediction_correct": None,
        "smtlib": None,
    }

    try:
        start_time = time.time()

        # Execute the constraint code (which creates its own builder and variables)
        # This avoids the duplicate constraint issue
        # Create a DateSMTBuilder factory that injects the approach parameter and timeout
        def create_builder():
            return DateSMTBuilder(approach=approach, timeout_ms=timeout_ms)
        
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

        # Check if prediction was correct
        actual_satisfiable = solve_result["status"] == "sat"
        result["prediction_correct"] = actual_satisfiable == expected_satisfiable

        if solve_result["status"] == "sat":
            print(f"✅ Solution found:")
            for name, date in result["solution"].items():
                print(f"  {name} = {date}")
        else:
            print(f"❌ No solution found")

        # Show prediction accuracy
        if result["prediction_correct"]:
            print(
                f"✅ Prediction correct (expected {expected_satisfiable}, got {actual_satisfiable})"
            )
        else:
            print(
                f"❌ Prediction incorrect (expected {expected_satisfiable}, got {actual_satisfiable})"
            )

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


def test_constraints_file(constraints_file: str, output_dir: str = "test_results", timeout_ms: int = 60000):
    """Test all constraints in a file with both approaches."""

    # Load constraints
    with open(constraints_file, 'r') as f:
        constraints = json.load(f)

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    smt_dir = os.path.join(output_dir, "smt2")
    os.makedirs(smt_dir, exist_ok=True)

    # Test with all three approaches
    approaches = ["baseline", "advanced", "hybrid"]
    all_results = {}

    for approach in approaches:
        print(f"\n{'='*60}")
        print(f"TESTING WITH {approach.upper()} APPROACH")
        print(f"{'='*60}")

        results = []
        for constraint in constraints:
            result = test_constraint_with_approach(constraint, approach, timeout_ms)
            # Save per-constraint SMT-LIB as .smt2 file
            if result.get("smtlib"):
                cid = _sanitize_filename(result.get("constraint_id", "unknown"))
                smt_path = os.path.join(smt_dir, f"{cid}_{approach}.smt2")
                try:
                    with open(smt_path, 'w') as f:
                        f.write(result["smtlib"])
                    # Attach path for traceability
                    result["smtlib_file"] = smt_path
                except Exception as e:
                    result["smtlib_file_error"] = str(e)
            results.append(result)

        all_results[approach] = results

        # Save results for this approach
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"results_{approach}_{timestamp}.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")

        # Print summary
        successful = len([r for r in results if r["status"] == "sat"])
        total = len(results)
        avg_time = sum(r["execution_time"] for r in results) / total if total > 0 else 0
        correct_predictions = len(
            [r for r in results if r.get("prediction_correct", False)]
        )

        print(f"\nSummary for {approach}:")
        print(f"  Successful: {successful}/{total} ({successful/total*100:.1f}%)")
        print(f"  Avg time: {avg_time:.4f}s")
        print(
            f"  Correct predictions: {correct_predictions}/{total} ({correct_predictions/total*100:.1f}%)"
        )


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
        "--output-dir", default="test_results", help="Output directory for results"
    )
    parser.add_argument(
        "--timeout", type=int, default=60000, help="Timeout in milliseconds (default: 60000 = 60 seconds)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.constraints_file):
        print(f"Error: Constraints file {args.constraints_file} not found")
        return

    test_constraints_file(args.constraints_file, args.output_dir, args.timeout)


if __name__ == "__main__":
    main()