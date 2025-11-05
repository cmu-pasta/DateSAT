"""
Enumeration baseline implementation for DATE-SMT.

This module provides a baseline solver that enumerates all valid dates
in the allowed range [1900-03-01 to 2100-02-28] and checks which assignments
satisfy the constraints. This is a brute-force approach that guarantees
finding a solution if one exists, but may be slow for large constraint sets.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, Optional, Union
import time
from .core import Date, Period


class ConstraintWrapper:
    """Wrapper for deferred constraint evaluation."""

    def __init__(self, func, description: str = "", var_ref=None, concrete_value=None, rhs_ref=None):
        """Create a constraint wrapper with a callable.

        Args:
            func: Function to evaluate the constraint
            description: Optional description
            var_ref: Reference to the LHS variable (for extracting bindings)
            concrete_value: Concrete value if this is an equality binding
            rhs_ref: Reference to the RHS (for extracting bindings from expressions)
        """
        self.func = func
        self.description = description
        self.var_ref = var_ref
        self.concrete_value = concrete_value
        self.rhs_ref = rhs_ref  # For equality constraints: x == expr, store expr here

    def evaluate(self) -> bool:
        """Evaluate the constraint."""
        try:
            return bool(self.func())
        except (ValueError, TypeError):
            return False

    def is_equality_binding(self) -> bool:
        """Check if this constraint binds a variable to a concrete value."""
        return self.concrete_value is not None and self.var_ref is not None

    def get_rhs_value(self) -> Optional[Date]:
        """Get the concrete value from the RHS if available."""
        if self.rhs_ref is not None:
            if isinstance(self.rhs_ref, Date):
                return self.rhs_ref
            elif hasattr(self.rhs_ref, 'get_value'):
                try:
                    return self.rhs_ref.get_value()
                except ValueError:
                    # Date is outside allowed range, return None
                    return None
        return None


class EnumerationDateVar:
    """Date variable for enumeration baseline that evaluates constraints concretely."""

    def __init__(self, name: str, year: int = None, month: int = None, day: int = None):
        """Create a date variable with optional concrete values."""
        self.name = name
        self._year = year
        self._month = month
        self._day = day
        self._value = None
        if year is not None and month is not None and day is not None:
            self._value = Date(year, month, day)

    def __str__(self) -> str:
        """Return a string representation of the EnumerationDateVar."""
        return f"EnumerationDateVar({self.name})"

    def set_value(self, year: int, month: int, day: int) -> None:
        """Set the concrete value for this variable."""
        self._year = year
        self._month = month
        self._day = day
        try:
            self._value = Date(year, month, day)
        except ValueError:
            self._value = None

    def get_value(self) -> Optional[Date]:
        """Get the current concrete Date value, computing lazy operations if needed."""
        # Handle lazy operations
        if self._value is None and hasattr(self, '_lazy_op'):
            op_type, left, right = self._lazy_op
            if op_type == 'add':
                left_val = left.get_value()
                if left_val is not None:
                    # Compute the result
                    py_date = left_val.to_python_date()
                    result_date = py_date + relativedelta(
                        years=right.years, months=right.months, days=right.days
                    )
                    result = Date.from_python_date(result_date)
                    self.set_value(result.year, result.month, result.day)
            elif op_type == 'sub':
                left_val = left.get_value()
                if left_val is not None:
                    # Compute the result
                    py_date = left_val.to_python_date()
                    neg_period = Period(-right.years, -right.months, -right.days)
                    result_date = py_date + relativedelta(
                        years=neg_period.years, months=neg_period.months, days=neg_period.days
                    )
                    result = Date.from_python_date(result_date)
                    self.set_value(result.year, result.month, result.day)
        return self._value

    def to_concrete_date(self) -> Date:
        """Get the concrete Date value (raises if not set)."""
        if self._value is None:
            raise ValueError(f"Date variable {self.name} has no concrete value")
        return self._value

    def _get_comparison_func(self, op: str, other: Union[Date, "EnumerationDateVar"]):
        """Create a deferred comparison function."""
        if isinstance(other, Date):
            other_date = other
            def compare():
                self_val = self.get_value()
                if self_val is None:
                    return False
                return getattr(self_val.to_python_date(), f"__{op}__")(other_date.to_python_date())
            return compare
        elif isinstance(other, EnumerationDateVar):
            other_ref = other
            def compare():
                self_val = self.get_value()
                other_val = other_ref.get_value()
                if self_val is None or other_val is None:
                    return False
                return getattr(self_val.to_python_date(), f"__{op}__")(
                    other_val.to_python_date()
                )
            return compare
        else:
            raise TypeError(f"Cannot compare EnumerationDateVar with {type(other)}")

    def _get_equality_binding(self, other: Union[Date, "EnumerationDateVar"]) -> Optional[Date]:
        """Extract concrete value from equality constraint if applicable."""
        if isinstance(other, Date):
            return other
        elif isinstance(other, EnumerationDateVar):
            return other.get_value()
        return None

    def __ge__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x >= date comparison."""
        return ConstraintWrapper(self._get_comparison_func("ge", other))

    def __le__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x <= date comparison."""
        return ConstraintWrapper(self._get_comparison_func("le", other))

    def __lt__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x < date comparison."""
        return ConstraintWrapper(self._get_comparison_func("lt", other))

    def __gt__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x > date comparison."""
        return ConstraintWrapper(self._get_comparison_func("gt", other))

    def __eq__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x == date comparison."""
        # If comparing to a concrete Date, this is a binding
        concrete_value = self._get_equality_binding(other)
        return ConstraintWrapper(
            self._get_comparison_func("eq", other),
            var_ref=self,
            concrete_value=concrete_value,
            rhs_ref=other  # Store RHS reference for later evaluation
        )

    def __ne__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        """Support x != date comparison."""
        return ConstraintWrapper(self._get_comparison_func("ne", other))

    def __add__(self, other: Period) -> "EnumerationDateVar":
        """EnumerationDateVar + Period using Python datetime."""
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to EnumerationDateVar")

        # If we don't have a value yet, compute it lazily when needed
        # Store the operation to compute when value is accessed
        result_var = EnumerationDateVar(
            f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
        )

        # Store operation for lazy evaluation
        result_var._lazy_op = ('add', self, other)

        # If we have a value now, compute immediately
        if self._value is not None:
            py_date = self._value.to_python_date()
            result_date = py_date + relativedelta(
                years=other.years, months=other.months, days=other.days
            )
            result = Date.from_python_date(result_date)
            result_var.set_value(result.year, result.month, result.day)

        return result_var

    def __sub__(self, other: Period) -> "EnumerationDateVar":
        """EnumerationDateVar - Period using Python datetime."""
        if not isinstance(other, Period):
            raise TypeError(f"Cannot subtract {type(other)} from EnumerationDateVar")

        # Similar to __add__, but for subtraction
        result_var = EnumerationDateVar(
            f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d"
        )

        # Store operation for lazy evaluation
        result_var._lazy_op = ('sub', self, other)

        # If we have a value now, compute immediately
        if self._value is not None:
            py_date = self._value.to_python_date()
            neg_period = Period(-other.years, -other.months, -other.days)
            result_date = py_date + relativedelta(
                years=neg_period.years, months=neg_period.months, days=neg_period.days
            )
            result = Date.from_python_date(result_date)
            result_var.set_value(result.year, result.month, result.day)

        return result_var


class EnumerationSolver:
    """Solver that enumerates all valid dates and checks constraints."""

    # Valid date range: [1900-03-01 to 2100-02-28]
    MIN_DATE = date(1900, 3, 1)
    MAX_DATE = date(2100, 2, 28)

    def __init__(self, timeout_ms: int = 600000):
        """Initialize the enumeration solver.

        Args:
            timeout_ms: Timeout in milliseconds (default: 600000 = 10 minutes)
        """
        self.date_vars: Dict[str, EnumerationDateVar] = {}
        self.constraints: list = []
        self.timeout_ms = timeout_ms
        self._cached_valid_dates = None  # Cache for valid dates list

    def add_date_var(self, name: str, year: int = None, month: int = None, day: int = None) -> EnumerationDateVar:
        """Add a date variable to the solver.

        Args:
            name: Variable name
            year: Optional year value (for validation mode)
            month: Optional month value (for validation mode)
            day: Optional day value (for validation mode)
        """
        if name not in self.date_vars:
            if year is not None and month is not None and day is not None:
                # Create variable with concrete values (validation mode)
                date_var = EnumerationDateVar(name, year, month, day)
            else:
                # Create variable without values (solving mode)
                date_var = EnumerationDateVar(name)
            self.date_vars[name] = date_var
        elif year is not None and month is not None and day is not None:
            # Update existing variable with values
            self.date_vars[name].set_value(year, month, day)
        return self.date_vars[name]

    def add_constraint(self, constraint: Any, description: str = "") -> None:
        """Add a constraint to the solver."""
        self.constraints.append(constraint)

    def check(self) -> str:
        """Check if constraints are satisfiable by enumerating all dates."""
        # Try to find a satisfying assignment
        solution = self._find_solution()
        if solution:
            return 'sat'
        else:
            return 'unsat'

    def _find_solution(self) -> Optional[Dict[str, Date]]:
        """Find a solution by enumerating all valid dates."""
        var_names = list(self.date_vars.keys())
        if not var_names:
            # No variables, check if constraints are trivially satisfied
            return self._evaluate_constraints({}) if self._evaluate_constraints({}) else None

        # Extract variable bindings from equality constraints iteratively
        # This handles cases like:
        # - x == Date(2020, 6, 15) → direct binding
        # - t0 == x + Period(1, 2, 3) → after x is bound, evaluate expression and bind t0
        concrete_vars = {}
        changed = True

        # Iteratively extract bindings until no more can be found
        while changed:
            changed = False

            # First, check for direct variable values (including from lazy operations)
            for var_name in var_names:
                if var_name not in concrete_vars:
                    date_var = self.date_vars[var_name]
                    value = date_var.get_value()  # This will evaluate lazy ops if dependencies are concrete
                    if value is not None:
                        concrete_vars[var_name] = value
                        changed = True

            # Then, extract bindings from equality constraints
            for constraint in self.constraints:
                if isinstance(constraint, ConstraintWrapper):
                    var_ref = constraint.var_ref
                    if var_ref is not None:
                        var_name = var_ref.name
                        if var_name not in concrete_vars:
                            # Try to get the concrete value from the constraint
                            # This handles both x == Date(...) and x == other_datevar
                            concrete_value = constraint.concrete_value

                            # If constraint.concrete_value is None, try to evaluate the RHS
                            # This handles cases like t0 == x + p where x just became concrete
                            if concrete_value is None:
                                rhs_value = constraint.get_rhs_value()
                                if rhs_value is not None:
                                    concrete_value = rhs_value

                            if concrete_value is not None:
                                # Bind the variable to the concrete value
                                concrete_vars[var_name] = concrete_value
                                self.date_vars[var_name].set_value(
                                    concrete_value.year, concrete_value.month, concrete_value.day
                                )
                                changed = True

            # Re-evaluate constraints to propagate bindings through expressions
            # This handles cases where t0 == x + p and x just became concrete
            for constraint in self.constraints:
                if isinstance(constraint, ConstraintWrapper):
                    var_ref = constraint.var_ref
                    if var_ref is not None:
                        var_name = var_ref.name
                        if var_name not in concrete_vars:
                            # Try to get value by evaluating the DateVar
                            # This will work if it's a lazy operation whose dependencies are now concrete
                            value = var_ref.get_value()
                            if value is not None:
                                concrete_vars[var_name] = value
                                self.date_vars[var_name].set_value(
                                    value.year, value.month, value.day
                                )
                                changed = True

        # Separate variables into concrete (bound) and symbolic (need enumeration)
        symbolic_vars = []
        for var_name in var_names:
            if var_name not in concrete_vars:
                symbolic_vars.append(var_name)

        # If all variables are concrete, just evaluate constraints directly (fast path)
        if not symbolic_vars:
            if self._evaluate_constraints(concrete_vars):
                return concrete_vars
            else:
                return None

        # Generate all valid dates for enumeration (only for symbolic variables)
        valid_dates = self._generate_all_valid_dates()

        # Only enumerate over symbolic variables
        from itertools import product

        num_symbolic = len(symbolic_vars)
        num_dates = len(valid_dates)

        if num_dates ** num_symbolic > 1000000:
            print(f"Warning: Large search space ({num_dates ** num_symbolic} combinations).")

        # Record start time for timeout checking
        start_time = time.time()
        timeout_seconds = self.timeout_ms / 1000.0

        # Try each combination for symbolic variables
        # Note: This will enumerate all possibilities. If it times out, it will timeout.
        for date_combination in product(valid_dates, repeat=num_symbolic):
            # Check timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                # Timeout exceeded - raise an exception or return None
                # We'll let the outer code handle timeout detection
                raise TimeoutError(f"Enumeration timeout after {elapsed_time:.2f} seconds (limit: {timeout_seconds:.2f}s)")

            # Create assignment: combine concrete and symbolic values
            assignment = concrete_vars.copy()
            for i, var_name in enumerate(symbolic_vars):
                d = date_combination[i]
                assignment[var_name] = Date(d.year, d.month, d.day)
                # Set the value in the date variable
                self.date_vars[var_name].set_value(d.year, d.month, d.day)

            # Evaluate constraints
            if self._evaluate_constraints(assignment):
                return assignment

        return None

    def _generate_all_valid_dates(self):
        """Generate all valid dates in the allowed range (cached)."""
        if self._cached_valid_dates is None:
            dates = []
            current = self.MIN_DATE
            while current <= self.MAX_DATE:
                try:
                    # Validate the date is in range
                    Date(current.year, current.month, current.day)
                    dates.append(current)
                except ValueError:
                    pass  # Skip invalid dates (shouldn't happen in range)

                # Move to next day
                current += timedelta(days=1)

            self._cached_valid_dates = dates

        return self._cached_valid_dates

    def _evaluate_constraints(self, assignment: Dict[str, Date]) -> bool:
        """Evaluate all constraints with the given assignment."""
        try:
            # Set all variable values
            for var_name, date_val in assignment.items():
                if var_name in self.date_vars:
                    self.date_vars[var_name].set_value(
                        date_val.year, date_val.month, date_val.day
                    )

            # Evaluate each constraint
            for constraint in self.constraints:
                # Constraints can be:
                # 1. Boolean values (from direct evaluation)
                # 2. ConstraintWrapper objects (from deferred evaluation)
                # 3. Callable objects that return boolean

                if isinstance(constraint, bool):
                    if not constraint:
                        return False
                elif isinstance(constraint, ConstraintWrapper):
                    if not constraint.evaluate():
                        return False
                elif callable(constraint):
                    if not constraint():
                        return False
                else:
                    # Try to evaluate as boolean
                    try:
                        result = bool(constraint)
                        if not result:
                            return False
                    except (TypeError, ValueError):
                        # If we can't evaluate, assume it's satisfied
                        pass

            return True
        except (ValueError, TypeError) as e:
            # If evaluation fails, assume constraint is not satisfied
            return False

    def model(self) -> Dict[str, Any]:
        """Get the model (returns current variable values if solution found)."""
        solution = self._find_solution()
        if solution:
            return {'dates': solution}
        else:
            return {'dates': {}}

    def get_concrete_dates(self) -> Dict[str, Date]:
        """Get concrete dates from the solver."""
        solution = self._find_solution()
        return solution if solution else {}

    def solve(self) -> Dict[str, Any]:
        """Solve the constraints and return results."""
        solution = self._find_solution()
        if solution:
            return {
                'status': 'sat',
                'dates': solution,
            }
        else:
            return {'status': 'unsat', 'dates': {}}

    def to_smt2(self) -> str:
        """Return empty SMT-LIB v2 format (not applicable for enumeration)."""
        return "; Enumeration baseline - no SMT-LIB output"

    def get_assertions(self) -> list:
        """Return the list of current constraints."""
        return self.constraints

    def validate_solution(self, solution: Dict[str, Date]) -> bool:
        """Validate a solution by checking if it satisfies all constraints.

        This is a convenience method for validation. It sets the solution values
        and evaluates all constraints.

        Args:
            solution: Dictionary mapping variable names to Date values

        Returns:
            True if all constraints are satisfied, False otherwise
        """
        return self._evaluate_constraints(solution)
