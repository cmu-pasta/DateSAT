"""
Fuzzing baseline implementation using hypothesis for DATE-SMT.

This module provides a baseline solver that uses Hypothesis property-based testing
to generate random date assignments and find solutions to constraints.
This is a fuzzing-based approach that may find solutions faster than enumeration
for some constraint sets, but is not guaranteed to find all solutions.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, Optional, Union
from hypothesis import strategies as st
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


class HypothesisDateVar:
    """Date variable for Hypothesis baseline that evaluates constraints concretely."""

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
        """Return a string representation of the HypothesisDateVar."""
        return f"HypothesisDateVar({self.name})"

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
        # Handle lazy operations (same as EnumerationDateVar)
        if self._value is None and hasattr(self, '_lazy_op'):
            op_type, left, right = self._lazy_op
            if op_type == 'add':
                left_val = left.get_value()
                if left_val is not None:
                    py_date = left_val.to_python_date()
                    result_date = py_date + relativedelta(
                        years=right.years, months=right.months, days=right.days
                    )
                    result = Date.from_python_date(result_date)
                    self.set_value(result.year, result.month, result.day)
            elif op_type == 'sub':
                left_val = left.get_value()
                if left_val is not None:
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

    def _get_comparison_func(self, op: str, other: Union[Date, "HypothesisDateVar"]):
        """Create a deferred comparison function."""
        if isinstance(other, Date):
            other_date = other
            def compare():
                self_val = self.get_value()
                if self_val is None:
                    return False
                return getattr(self_val.to_python_date(), f"__{op}__")(other_date.to_python_date())
            return compare
        elif isinstance(other, HypothesisDateVar):
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
            raise TypeError(f"Cannot compare HypothesisDateVar with {type(other)}")

    def _get_equality_binding(self, other: Union[Date, "HypothesisDateVar"]) -> Optional[Date]:
        """Extract concrete value from equality constraint if applicable."""
        if isinstance(other, Date):
            return other
        elif isinstance(other, HypothesisDateVar):
            return other.get_value()
        return None

    def __ge__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x >= date comparison."""
        return ConstraintWrapper(self._get_comparison_func("ge", other))

    def __le__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x <= date comparison."""
        return ConstraintWrapper(self._get_comparison_func("le", other))

    def __lt__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x < date comparison."""
        return ConstraintWrapper(self._get_comparison_func("lt", other))

    def __gt__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x > date comparison."""
        return ConstraintWrapper(self._get_comparison_func("gt", other))

    def __eq__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x == date comparison."""
        # If comparing to a concrete Date, this is a binding
        concrete_value = self._get_equality_binding(other)
        return ConstraintWrapper(
            self._get_comparison_func("eq", other),
            var_ref=self,
            concrete_value=concrete_value,
            rhs_ref=other  # Store RHS reference for later evaluation
        )

    def __ne__(self, other: Union[Date, "HypothesisDateVar"]) -> "ConstraintWrapper":
        """Support x != date comparison."""
        return ConstraintWrapper(self._get_comparison_func("ne", other))

    def __add__(self, other: Period) -> "HypothesisDateVar":
        """HypothesisDateVar + Period using Python datetime."""
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to HypothesisDateVar")

        result_var = HypothesisDateVar(
            f"{self.name}_plus_{other.years}y_{other.months}m_{other.days}d"
        )
        result_var._lazy_op = ('add', self, other)

        if self._value is not None:
            py_date = self._value.to_python_date()
            result_date = py_date + relativedelta(
                years=other.years, months=other.months, days=other.days
            )
            result = Date.from_python_date(result_date)
            result_var.set_value(result.year, result.month, result.day)

        return result_var

    def __sub__(self, other: Period) -> "HypothesisDateVar":
        """HypothesisDateVar - Period using Python datetime."""
        if not isinstance(other, Period):
            raise TypeError(f"Cannot subtract {type(other)} from HypothesisDateVar")

        result_var = HypothesisDateVar(
            f"{self.name}_minus_{other.years}y_{other.months}m_{other.days}d"
        )
        result_var._lazy_op = ('sub', self, other)

        if self._value is not None:
            py_date = self._value.to_python_date()
            neg_period = Period(-other.years, -other.months, -other.days)
            result_date = py_date + relativedelta(
                years=neg_period.years, months=neg_period.months, days=neg_period.days
            )
            result = Date.from_python_date(result_date)
            result_var.set_value(result.year, result.month, result.day)

        return result_var


class HypothesisSolver:
    """Solver that uses Hypothesis fuzzing to find solutions."""

    # Valid date range: [1900-03-01 to 2100-02-28]
    MIN_DATE = date(1900, 3, 1)
    MAX_DATE = date(2100, 2, 28)

    def __init__(self, timeout_ms: int = 60000, max_examples: int = 10000):
        """Initialize the Hypothesis solver.

        Args:
            timeout_ms: Timeout in milliseconds (not directly used by Hypothesis)
            max_examples: Maximum number of examples to try before giving up
        """
        self.date_vars: Dict[str, HypothesisDateVar] = {}
        self.constraints: list = []
        self.timeout_ms = timeout_ms
        self.max_examples = max_examples

    def add_date_var(self, name: str) -> HypothesisDateVar:
        """Add a date variable to the solver."""
        if name not in self.date_vars:
            date_var = HypothesisDateVar(name)
            self.date_vars[name] = date_var
        return self.date_vars[name]

    def add_constraint(self, constraint: Any, description: str = "") -> None:
        """Add a constraint to the solver."""
        self.constraints.append(constraint)

    def check(self) -> str:
        """Check if constraints are satisfiable using Hypothesis fuzzing."""
        solution = self._find_solution()
        if solution:
            return 'sat'
        else:
            return 'unsat'

    def _find_solution(self) -> Optional[Dict[str, Date]]:
        """Find a solution using Hypothesis fuzzing."""
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

        # Separate variables into concrete (bound) and symbolic (need fuzzing)
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

        # Create a Hypothesis strategy for generating valid dates (only for symbolic variables)
        date_strategy = self._create_date_strategy()

        # Create a strategy for generating assignments to symbolic variables only
        # We need to generate a tuple of dates, one for each symbolic variable
        var_strategy = st.tuples(*[date_strategy for _ in symbolic_vars])

        # Track tested combinations to avoid retesting (Hypothesis can generate duplicates)
        # Use tuple of date tuples for hashability
        tested_combinations = set()
        max_tested_combinations = 1000000  # Limit to prevent excessive memory usage

        # Try to find a satisfying assignment by sampling from the strategy
        attempt_count = 0
        while attempt_count < self.max_examples:
            try:
                # Generate a random example for symbolic variables
                date_tuple = var_strategy.example()

                # Convert to assignment dictionary: combine concrete and fuzzed values
                assignment = concrete_vars.copy()
                date_tuple_list = []
                for i, var_name in enumerate(symbolic_vars):
                    d = date_tuple[i]
                    try:
                        date_obj = Date(d.year, d.month, d.day)
                        assignment[var_name] = date_obj
                        date_tuple_list.append((date_obj.year, date_obj.month, date_obj.day))
                    except ValueError:
                        # Skip invalid dates
                        break
                else:
                    # All dates were valid, check if we've tested this combination before
                    combination_key = tuple(date_tuple_list)
                    if combination_key in tested_combinations:
                        # Skip this duplicate combination
                        attempt_count += 1
                        continue

                    # Add to tested set (if not at limit)
                    if len(tested_combinations) < max_tested_combinations:
                        tested_combinations.add(combination_key)

                    # Test the assignment
                    if self._evaluate_constraints(assignment):
                        return assignment
            except Exception:
                # Continue on errors
                pass

            attempt_count += 1

        return None

    def _create_date_strategy(self):
        """Create a Hypothesis strategy for generating valid dates."""
        # Generate dates in the valid range
        return st.dates(
            min_value=self.MIN_DATE,
            max_value=self.MAX_DATE
        )

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
                    try:
                        result = bool(constraint)
                        if not result:
                            return False
                    except (TypeError, ValueError):
                        pass

            return True
        except (ValueError, TypeError):
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
        """Return empty SMT-LIB v2 format (not applicable for Hypothesis)."""
        return "; Hypothesis baseline - no SMT-LIB output"

    def get_assertions(self) -> list:
        """Return the list of current constraints."""
        return self.constraints
