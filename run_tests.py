#!/usr/bin/env python3
"""
Test runner script for DATE-SMT unit tests.

This script provides a convenient way to run tests with different configurations.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print("Make sure pytest is installed: pip install -r tests/requirements.txt")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run DATE-SMT tests")
    parser.add_argument(
        "--category",
        choices=[
            "unit",
            "property",
            "integration",
            "core",
            "validation",
            "algorithm",
            "all",
        ],
        default="all",
        help="Test category to run",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Run tests in verbose mode"
    )
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")

    args = parser.parse_args()

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add test path based on category
    if args.category == "all":
        cmd.append("tests/")
    elif args.category == "unit":
        cmd.append("tests/unit_tests/")
    elif args.category == "property":
        cmd.append("tests/property_tests/")
    elif args.category == "integration":
        cmd.append("tests/integration_tests/")
    elif args.category == "core":
        cmd.append("tests/unit_tests/core_data_structures/")
    elif args.category == "validation":
        cmd.append("tests/unit_tests/date_validation/")
    elif args.category == "algorithm":
        cmd.append("tests/unit_tests/algorithm_specific/")

    # Add options
    if args.verbose:
        cmd.append("-v")

    if args.coverage:
        cmd.extend(["--cov=datesmt", "--cov-report=html", "--cov-report=term"])

    if args.parallel:
        cmd.extend(["-n", "auto"])

    # Run the tests
    success = run_command(cmd, f"Tests for {args.category} category")

    if success:
        print(f"\n🎉 All tests completed successfully!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
