#!/usr/bin/env python3
"""
Command-line interface for DateSMT.

Usage:
    ./bin/datesmt.py < constraints.json
    ./bin/datesmt.py --file constraints.json
    ./bin/datesmt.py --approach hybrid --implementation bitvector < constraints.json
    
The input should be a JSON file with the following format:
{
    "declarations": ["x: date", "y: date", "n: int"],
    "constraints": [
        "x >= Date(2000,1,1)",
        "y == x + Period(0,1,0)",
        "n > 5"
    ]
}
"""

import argparse
import json
import sys
import os

# Add the parent directory to the path so we can import datesmt
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import datesmt


def format_solution(result: dict) -> str:
    """Format the solution for pretty printing."""
    lines = []
    
    if result["status"] == "sat":
        lines.append("✅ SATISFIABLE\n")
        lines.append("Solution:")
        
        # Print dates
        for name, date_obj in result.get("dates", {}).items():
            lines.append(f"  {name} = {date_obj}")
        
        # Print integers
        for name, value in result.get("ints", {}).items():
            lines.append(f"  {name} = {value}")
        
        # Print booleans
        for name, value in result.get("bools", {}).items():
            lines.append(f"  {name} = {value}")
    else:
        lines.append("❌ UNSATISFIABLE")
    
    # Add metadata
    lines.append(f"\nExecution time: {result['execution_time']:.3f}s")
    lines.append(f"Approach: {result['approach']}")
    lines.append(f"Implementation: {result['implementation']}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="DateSMT: A framework for symbolic analysis of date-based computations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read from stdin
  ./bin/datesmt.py < constraints.json
  cat constraints.json | ./bin/datesmt.py
  
  # Read from file
  ./bin/datesmt.py --file constraints.json
  
  # Use different approach and implementation
  ./bin/datesmt.py --approach hybrid --implementation bitvector < constraints.json
  
  # Get JSON output
  ./bin/datesmt.py --output json < constraints.json
  
Input format:
  {
    "declarations": ["x: date", "y: date", "n: int"],
    "constraints": [
      "x >= Date(2000,1,1)",
      "y == x + Period(0,1,0)",
      "n > 5"
    ]
  }
        """
    )
    
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Input JSON file (if not provided, reads from stdin)"
    )
    
    parser.add_argument(
        "-a", "--approach",
        type=str,
        default="epoch_days",
        choices=["naive", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"],
        help="Solver approach (default: epoch_days)"
    )
    
    parser.add_argument(
        "-i", "--implementation",
        type=str,
        default="int",
        choices=["int", "bitvector"],
        help="Implementation type (default: int)"
    )
    
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=600000,
        help="Timeout in milliseconds (default: 600000 = 10 minutes)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="human",
        choices=["human", "json"],
        help="Output format (default: human)"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress solver output (only show final result)"
    )
    
    parser.add_argument(
        "--maxsat",
        action="store_true",
        help="Use MaxSAT optimization with soft constraints for dates near today"
    )
    
    args = parser.parse_args()
    
    # Read input
    try:
        if args.file:
            with open(args.file, 'r') as f:
                json_data = f.read()
        else:
            json_data = sys.stdin.read()
        
        constraint_data = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Validate input format
    if not isinstance(constraint_data, dict):
        print("Error: Input must be a JSON object with 'constraints' field", file=sys.stderr)
        sys.exit(1)
    
    if "constraints" not in constraint_data:
        print("Error: Input must contain 'constraints' field", file=sys.stderr)
        sys.exit(1)
    
    # Solve
    try:
        result = datesmt.solve(
            constraints=constraint_data,
            approach=args.approach,
            implementation=args.implementation,
            timeout_ms=args.timeout,
            verbose=not args.quiet,
            use_maxsat=args.maxsat
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    
    # Output result
    if args.output == "json":
        # Convert Date objects to strings for JSON serialization
        output = {**result}
        if "dates" in output:
            output["dates"] = {
                name: str(date) for name, date in output["dates"].items()
            }
        print(json.dumps(output, indent=2))
    else:
        # Suppress the solver's output since we already printed it
        if not args.quiet:
            print()  # Add a blank line for readability
        print(format_solution(result))
    
    # Exit with appropriate code
    sys.exit(0 if result["status"] == "sat" else 1)


if __name__ == "__main__":
    main()
