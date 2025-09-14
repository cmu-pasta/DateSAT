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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'datesmt'))

try:
    from datesmt.core import Date, Period
    from datesmt.symbolic_api import DateSMTBuilder
except ImportError:
    # Fallback for when running from different directory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from datesmt.core import Date, Period
    from datesmt.symbolic_api import DateSMTBuilder


def test_constraint_with_approach(constraint_data: dict, approach: str) -> dict:
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
    }

    try:
        start_time = time.time()

        # Create solver
        builder = DateSMTBuilder(approach)

        # Add variables
        var_objects = {}
        for var in variables:
            if var in ['x', 'y', 'z']:
                var_objects[var] = builder.add_date_var(var)
            elif var in ['p', 'q', 'r']:
                var_objects[var] = builder.add_period_var(var)

        # Execute the constraint code
        exec_globals = {
            'Date': Date,
            'Period': Period,
            'builder': builder,
            'add_constraint': builder.add_constraint,
            **var_objects,
        }

        exec(constraint_code, exec_globals)

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

    except Exception as e:
        result["error_message"] = str(e)
        print(f"❌ Error: {e}")

    return result


def test_constraints_file(constraints_file: str, output_dir: str = "test_results"):
    """Test all constraints in a file with both approaches."""

    # Load constraints
    with open(constraints_file, 'r') as f:
        constraints = json.load(f)

    print(f"Loaded {len(constraints)} constraints from {constraints_file}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Test with both approaches
    approaches = ["baseline", "advanced"]
    all_results = {}

    for approach in approaches:
        print(f"\n{'='*60}")
        print(f"TESTING WITH {approach.upper()} APPROACH")
        print(f"{'='*60}")

        results = []
        for constraint in constraints:
            result = test_constraint_with_approach(constraint, approach)
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

    # Compare approaches
    print(f"\n{'='*60}")
    print("APPROACH COMPARISON")
    print(f"{'='*60}")

    baseline_results = all_results["baseline"]
    advanced_results = all_results["advanced"]

    status_matches = 0
    prediction_accuracy_baseline = 0
    prediction_accuracy_advanced = 0

    for i, (baseline, advanced) in enumerate(zip(baseline_results, advanced_results)):
        match = baseline["status"] == advanced["status"]
        if match:
            status_matches += 1

        if baseline.get("prediction_correct"):
            prediction_accuracy_baseline += 1
        if advanced.get("prediction_correct"):
            prediction_accuracy_advanced += 1

        print(
            f"{baseline['constraint_id']}: {baseline['status']} vs {advanced['status']} {'✅' if match else '❌'}"
        )

    print(
        f"\nStatus matches: {status_matches}/{len(baseline_results)} ({status_matches/len(baseline_results)*100:.1f}%)"
    )
    print(
        f"Prediction accuracy - Baseline: {prediction_accuracy_baseline}/{len(baseline_results)} ({prediction_accuracy_baseline/len(baseline_results)*100:.1f}%)"
    )
    print(
        f"Prediction accuracy - Advanced: {prediction_accuracy_advanced}/{len(advanced_results)} ({prediction_accuracy_advanced/len(advanced_results)*100:.1f}%)"
    )

    # Coverage analysis
    print(f"\n{'='*60}")
    print("COVERAGE ANALYSIS")
    print(f"{'='*60}")

    all_tags = set()
    for constraint in constraints:
        all_tags.update(constraint.get("coverage_tags", []))

    print(f"Coverage tags found: {', '.join(sorted(all_tags))}")

    for tag in sorted(all_tags):
        tag_constraints = [c for c in constraints if tag in c.get("coverage_tags", [])]
        print(f"\n{tag}: {len(tag_constraints)} constraints")

        # Show success rate for this tag
        for approach in approaches:
            tag_results = [
                r for r in all_results[approach] if tag in r.get("coverage_tags", [])
            ]
            if tag_results:
                successful = len([r for r in tag_results if r["status"] == "sat"])
                print(f"  {approach}: {successful}/{len(tag_results)} successful")

    # Save comparison
    comparison = {
        "timestamp": datetime.now().isoformat(),
        "total_constraints": len(constraints),
        "status_matches": status_matches,
        "match_rate": status_matches / len(baseline_results),
        "coverage_tags": list(all_tags),
        "baseline_summary": {
            "successful": len([r for r in baseline_results if r["status"] == "sat"]),
            "avg_time": sum(r["execution_time"] for r in baseline_results)
            / len(baseline_results),
            "prediction_accuracy": prediction_accuracy_baseline / len(baseline_results),
        },
        "advanced_summary": {
            "successful": len([r for r in advanced_results if r["status"] == "sat"]),
            "avg_time": sum(r["execution_time"] for r in advanced_results)
            / len(advanced_results),
            "prediction_accuracy": prediction_accuracy_advanced / len(advanced_results),
        },
    }

    comparison_file = os.path.join(
        output_dir, f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    print(f"\nComparison saved to: {comparison_file}")


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

    args = parser.parse_args()

    if not os.path.exists(args.constraints_file):
        print(f"Error: Constraints file {args.constraints_file} not found")
        return

    test_constraints_file(args.constraints_file, args.output_dir)


if __name__ == "__main__":
    main()
