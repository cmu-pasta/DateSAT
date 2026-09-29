"""
High-level solver API for DateSAT.

This module provides an interface for solving date constraints.
"""

import json
from typing import Any, Dict, List, Union
from z3 import BoolVal
from . import router
from .api import DateSATBuilder
from .constraint_parser import ConstraintParser
from .core import Date, Period


def solve(
    constraints: Union[List[str], Dict[str, Any]],
    declarations: List[str] = None,
    approach: str = "epoch_days",
    implementation: str = "int",
    timeout_ms: int = 600000,
    verbose: bool = True,
    use_maxsat: bool = False,
) -> Dict[str, Any]:
    """
    Solve date constraints and return the result.
    
    This is the main high-level API for DateSAT. It accepts constraints in either
    a simple list format or the full JSON format used in DateSATBench.
    
    Args:
        constraints: Either:
            - A list of constraint strings, e.g., ["x >= Date(2000,1,1)", "x < y"]
            - A dict with "constraints" and "declarations" fields (JSON format)
        declarations: Optional list of variable declarations, e.g., ["x: date", "y: date"]
            Only used if constraints is a list. If constraints is a dict, declarations
            are taken from the dict.
        approach: Solver approach. For int implementation: "simple", "epoch_days", "hybrid_ymd",
            "hybrid_epoch", "alpha_beta", "alpha_beta_table", or "router", which picks one of
            the others per constraint with a trained model (see docs/router.md). For bitvector
            implementation: "simple", "epoch_days", "hybrid", "alpha_beta", or "alpha_beta_table".
        implementation: Implementation type - "int" or "bitvector"
        timeout_ms: Timeout in milliseconds (default: 600000 = 10 minutes)
        verbose: If True, print results to stdout (default: True)
    
    Returns:
        Dictionary with:
            - status: "sat" or "unsat"
            - dates: Dict mapping date variable names to Date objects (if sat)
            - ints: Dict mapping int variable names to int values (if sat)
            - bools: Dict mapping bool variable names to bool values (if sat)
            - execution_time: Time taken to solve in seconds (build_time + solve_time)
            - build_time: Seconds spent building the constraints into the solver
            - solve_time: Seconds spent in the solver check and model extraction
            - approach: The approach used
            - implementation: The implementation used
            - routed_to: For approach "router", the encoding the router picked
            - routing_time: For approach "router", seconds spent picking it (part of
              execution_time)
    
    Examples:
        >>> # API usage
        >>> result = datesat.solve(
        ...     constraints=["x >= Date(2000,1,1)", "x < Date(2000,12,31)"],
        ...     declarations=["x: date"]
        ... )
        
        >>> # JSON format usage
        >>> result = datesat.solve({
        ...     "declarations": ["x: date", "y: date"],
        ...     "constraints": ["x >= Date(2000,1,1)", "y == x + Period(0,1,0)"]
        ... })
        
        >>> # With integer variables
        >>> result = datesat.solve({
        ...     "declarations": ["x: date", "n: int"],
        ...     "constraints": ["x == Date(2000,1,1) + Period(0,0,n)", "n > 5", "n < 10"]
        ... })
    """
    import time
    
    # Parse constraint format
    if isinstance(constraints, dict):
        constraint_data = constraints
    else:
        constraint_data = {
            "constraints": constraints,
            "declarations": declarations or []
        }
    
    # Parse constraints into executable code
    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)
    
    if approach == "router":
        if implementation != "int":
            raise ValueError("the router approach only routes to int encodings; "
                             "use implementation='int'")
        router.load_model()   # once per process, and not part of the solve time

    # Create builder and execution context
    start_time = time.time()

    # The router picks the encoding inside the timed region, so execution_time includes it.
    routed_to = routing_time = None
    if approach == "router":
        routed_to, routing_time = router.route(constraint_data)
    builder_approach = routed_to or approach

    # Create a builder factory that will be used in the executed code
    def create_builder():
        return DateSATBuilder(
            approach=builder_approach,
            implementation=implementation,
            timeout_ms=timeout_ms,
            use_maxsat=use_maxsat
        )
    
    # Set up execution context with all necessary imports and the builder factory
    exec_globals = {
        "DateSATBuilder": create_builder,
        "Date": Date,
        "Period": Period,
    }
    
    # Execute the constraint code, catching ValueError for out-of-bounds dates and converting to UNSAT
    try:
        exec(constraint_code, exec_globals)
    except ValueError as e:
        # Check if this is a date out of bounds error
        if "Date outside allowed range" in str(e):
            # Intermediate date went out of bounds - add a False constraint to make it UNSAT
            builder = exec_globals.get("builder")
            if builder:
                builder.add_constraint(BoolVal(False))
            else:
                # If builder doesn't exist yet, we can't add constraint, so re-raise
                raise RuntimeError(f"Date out of bounds during constraint setup: {e}") from e
        else:
            # Re-raise if it's a different ValueError
            raise
    
    # Get the builder from executed code
    builder = exec_globals.get("builder")
    if not builder:
        raise RuntimeError("Failed to create constraint solver")

    build_time = time.time() - start_time

    # Temporarily disable builder's verbose output if verbose=False
    if not verbose:
        original_solve = builder.solve
        def quiet_solve():
            # Capture and suppress output
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                result = original_solve()
            finally:
                sys.stdout = old_stdout
            return result
        builder.solve = quiet_solve
    
    # Solve the constraints
    solve_result = builder.solve()
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Add metadata to result
    result = {
        **solve_result,
        "execution_time": execution_time,
        "build_time": build_time,
        "solve_time": execution_time - build_time,
        "approach": approach,
        "implementation": implementation,
    }
    if routed_to is not None:
        result["routed_to"] = routed_to
        result["routing_time"] = routing_time

    return result


def solve_from_json(json_data: Union[str, Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """
    Solve constraints from JSON data.
    
    Args:
        json_data: Either a JSON string or a parsed dictionary
        **kwargs: Additional arguments to pass to solve()
    
    Returns:
        Dictionary with solution results
    
    Examples:
        >>> # From JSON string
        >>> result = datesat.solve_from_json('''
        ... {
        ...     "declarations": ["x: date"],
        ...     "constraints": ["x >= Date(2000,1,1)"]
        ... }
        ... ''')
        
        >>> # From file
        >>> with open('constraints.json') as f:
        ...     result = datesat.solve_from_json(f.read())
    """
    if isinstance(json_data, str):
        constraint_data = json.loads(json_data)
    else:
        constraint_data = json_data
    
    return solve(constraint_data, **kwargs)
