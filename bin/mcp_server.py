#!/usr/bin/env python3
"""
MCP Server for DateSAT.

This module implements a Model Context Protocol (MCP) server that exposes
DateSAT's constraint solving capabilities to AI agents.

The server provides a 'solve' tool that accepts date constraint specifications
and returns satisfiability results with satisfying assignments.
"""

import os
import sys

# Add the parent directory to the path so we can import datesat
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mcp.server.fastmcp import FastMCP
from typing import Optional
import datesat

# Create the MCP server instance
mcp = FastMCP(
    "DateSAT",
    instructions="A symbolic solver for date constraints using Z3 SMT solver. "
    "Use the 'solve' tool to find date values that satisfy given constraints."
)


@mcp.tool()
def solve(
    declarations: list[str],
    constraints: list[str],
    approach: str = "epoch_days",
    implementation: str = "int",
    timeout_ms: int = 600000
) -> dict:
    """
    Solve date constraints and return satisfying assignments if satisfiable.

    This tool uses the Z3 SMT solver to find date values that satisfy all
    given constraints. It supports date arithmetic, period operations,
    and various comparison operators.

    Args:
        declarations: List of variable declarations in the format "name: type"
                     where type is one of: Date, int, bool
                     Examples: ["x: Date", "y: Date", "n: int", "flag: bool"]

        constraints: List of constraint expressions to satisfy. All constraints
                    are ANDed together. Supported syntax includes:
                    - Date constructors: Date(year, month, day)
                    - Period constructors: Period(years, months, days)
                    - Date arithmetic: date + period, date - period
                    - Period arithmetic: period + period, period - period, int * period
                    - Comparisons: ==, !=, <, <=, >, >=
                    - Date components: date.year, date.month, date.day
                    - Boolean operators: && (and), || (or), ! (not), -> (implies)
                    Examples:
                    - "x >= Date(2024, 1, 1)"
                    - "y == x + Period(1, 0, 0)"
                    - "x.month == 6"
                    - "(x.year == 2024) -> (flag == True)"

        approach: Solver approach to use. Options:
                 - "epoch_days" (default, recommended): Convert dates to days since epoch
                 - "naive": Direct encoding of date arithmetic
                 - "hybrid": Hybrid approach combining multiple encodings
                 - "alpha_beta": Alpha-beta encoding for optimized arithmetic
                 - "alpha_beta_table": Table-based alpha-beta encoding

        implementation: Implementation type for Z3 encoding. Options:
                       - "int" (default): Use integer arithmetic
                       - "bitvector": Use bitvector arithmetic

        timeout_ms: Solver timeout in milliseconds (default: 600000 = 10 minutes)

    Returns:
        A dictionary containing:
        - status: One of:
            - "sat": Constraints are satisfiable (solution found)
            - "unsat": Constraints are unsatisfiable (no solution exists)
            - "timeout": Solver timed out before finding a solution
            - "error": An error occurred (e.g., syntax error in constraints)
        - dates: Dictionary mapping date variable names to their values (if sat)
                 Values are strings in "Date(YYYY, M, D)" format
        - ints: Dictionary mapping integer variable names to their values (if sat)
        - bools: Dictionary mapping boolean variable names to their values (if sat)
        - execution_time: Time taken to solve in seconds (not present on error)
        - approach: The solver approach used (not present on error)
        - implementation: The implementation type used (not present on error)
        - error: Error message (only present when status is "error")

    Examples:
        # Find a date in June 2024
        solve(
            declarations=["x: Date"],
            constraints=["x >= Date(2024, 6, 1)", "x <= Date(2024, 6, 30)"]
        )
        # Returns: {"status": "sat", "dates": {"x": "Date(2024, 6, 1)"}, ...}

        # Find two dates where y is one year after x
        solve(
            declarations=["x: Date", "y: Date"],
            constraints=["x >= Date(2024, 1, 1)", "y == x + Period(1, 0, 0)"]
        )

        # Unsatisfiable constraints
        solve(
            declarations=["x: Date"],
            constraints=["x < Date(2024, 1, 1)", "x > Date(2024, 12, 31)"]
        )
        # Returns: {"status": "unsat", ...}

    Notes:
        - Date range: All dates must be between 1900-03-01 and 2100-02-28
        - Period range: Years +/-200, Months +/-2400, Days +/-73048
        - date - date is not supported (use periods instead)
    """
    # Validate approach
    valid_approaches = ["naive", "epoch_days", "hybrid", "alpha_beta", "alpha_beta_table"]
    if approach not in valid_approaches:
        return {
            "status": "error",
            "error": f"Invalid approach '{approach}'. Must be one of: {valid_approaches}"
        }

    # Validate implementation
    valid_implementations = ["int", "bitvector"]
    if implementation not in valid_implementations:
        return {
            "status": "error",
            "error": f"Invalid implementation '{implementation}'. Must be one of: {valid_implementations}"
        }

    try:
        result = datesat.solve(
            constraints={
                "declarations": declarations,
                "constraints": constraints
            },
            approach=approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            verbose=False
        )

        # Convert Date objects to strings for JSON serialization
        output = {
            "status": result["status"],
            "execution_time": result["execution_time"],
            "approach": result["approach"],
            "implementation": result["implementation"]
        }

        if result["status"] == "sat":
            if "dates" in result:
                output["dates"] = {
                    name: str(date) for name, date in result["dates"].items()
                }
            if "ints" in result:
                output["ints"] = result["ints"]
            if "bools" in result:
                output["bools"] = result["bools"]

        return output

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def create_sse_app():
    """Create and return the SSE application for use with ASGI servers."""
    return mcp.sse_app()


# Pre-create the SSE app for uvicorn import
sse_app = mcp.sse_app()


if __name__ == "__main__":
    # When run directly, start the server using stdio transport
    # For HTTP/SSE, use the launch script
    mcp.run()
