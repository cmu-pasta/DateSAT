"""
Test runner for Title 26 extracted constraints.

Similar to dataset/LLM_gen_constraints/run_tests.py, this script tests
constraints extracted from Title 26 with multiple DateSMT approaches.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import from the LLM run_tests module
from dataset.LLM_gen_constraints.run_tests import (
    filter_methods,
    run_constraints_file,
)


def main():
    """Main function to run constraint testing and analysis."""
    parser = argparse.ArgumentParser(
        description="Test Title 26 extracted constraints with DATE-SMT and optionally analyze results"
    )
    parser.add_argument(
        "constraints_file",
        help="JSON file containing extracted constraints (relative to repository root or absolute path)",
    )
    parser.add_argument(
        "--output-dir",
        default="dataset/law/processed_data/results",
        help="Output directory for results (default: dataset/law/processed_data/results)",
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

    # Resolve constraints file path
    constraints_path = Path(args.constraints_file)
    if not constraints_path.is_absolute():
        constraints_path = Path(REPO_ROOT) / constraints_path

    if not constraints_path.exists():
        print(f"Error: Constraints file {constraints_path} not found")
        return

    # Determine if analysis should run
    run_analysis = args.analysis and not args.no_analysis

    print(f"Running constraint tests for Title 26 extracted constraints...")
    print(f"Constraints file: {constraints_path}")
    print(f"Analysis: {'Enabled' if run_analysis else 'Disabled'}")
    if args.methods:
        print(f"Methods: {', '.join(args.methods)}")
    else:
        print(f"Methods: All methods (default)")

    # Run constraint execution using the shared function
    all_results = run_constraints_file(
        str(constraints_path),
        args.output_dir,
        args.timeout,
        methods=args.methods
    )

    if run_analysis:
        print(f"\n{'='*60}")
        print("RUNNING ANALYSIS")
        print(f"{'='*60}")

        results_dir = Path(args.output_dir)
        if not results_dir.exists() or not results_dir.is_dir():
            print(f"Error: Results directory not found: {results_dir}")
            return

        # Import validation function
        from dataset.validation import check_results_dir

        summary = check_results_dir(results_dir, enumeration_filter="supported")

        # Save analysis results (enumeration-supported constraints)
        analysis_output = results_dir / "checked_summary.json"
        with open(analysis_output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=False)

        print(f"\nAnalysis complete!")
        print(
            f"Checked {summary['constraints_checked']} constraints "
            "(enumeration supported)"
        )
        print(f"Analysis results saved to: {analysis_output}")

        # Also save stats for constraints not supported by enumeration baseline
        enum_support = summary.get("enumeration_support", {})
        not_supported_count = enum_support.get("not_supported_count", 0)
        if not_supported_count:
            unsupported_summary = check_results_dir(
                results_dir, enumeration_filter="not_supported"
            )
            unsupported_output = results_dir / "checked_summary_not_supported.json"
            with open(unsupported_output, "w", encoding="utf-8") as f:
                json.dump(unsupported_summary, f, indent=2, sort_keys=False)
            print(
                f"Constraints without enumeration support: {not_supported_count} "
                f"(saved to: {unsupported_output})"
            )

        # Print summary statistics
        counts = summary.get('counts_by_approach', {})
        if counts:
            print(f"\nSummary by approach (enumeration supported constraints):")
            for approach, counts_dict in counts.items():
                total = sum(counts_dict.values())
                correct = counts_dict.get('correct', 0)
                print(f"  {approach}: {correct}/{total} correct ({correct/total*100:.1f}%)")


if __name__ == "__main__":
    main()
