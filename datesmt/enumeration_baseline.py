"""
Enumeration baseline implementation for DATE-SMT.

This module provides a baseline solver that enumerates all valid dates
in the allowed range [1900-03-01 to 2100-02-28] and checks which assignments
satisfy the constraints. This is a brute-force approach that guarantees
finding a solution if one exists, but may be slow for large constraint sets.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, Optional, Union, List
import time
from .core import Date, Period


class ConstraintWrapper:
    """Wrapper for deferred constraint evaluation."""

    def __init__(self, func, var_ref=None, concrete_value=None, rhs_ref=None, or_constraints=None):
        self.func = func
        self.var_ref = var_ref
        self.concrete_value = concrete_value
        self.rhs_ref = rhs_ref  # For equality constraints: x == expr, store expr here
        self.or_constraints = or_constraints  # For OR constraints: list of ConstraintWrapper objects

    def evaluate(self) -> bool:
        try:
            # If this is an OR constraint, evaluate any of the sub-constraints
            if self.or_constraints is not None:
                return any(c.evaluate() for c in self.or_constraints)
            return bool(self.func())
        except (ValueError, TypeError):
            return False

    def is_equality_binding(self) -> bool:
        """Check if this is an equality constraint that can bind a variable.
        
        Returns True if:
        - Has a concrete value (direct binding: x == Date(...))
        - OR has a var_ref and rhs_ref (can be evaluated: x == y or x == y + Period(...))
        """
        if self.var_ref is None:
            return False
        # Direct binding with concrete value
        if self.concrete_value is not None:
            return True
        # Equality constraint with RHS that can be evaluated (variable or lazy operation)
        if self.rhs_ref is not None:
            return True
        return False

    def get_rhs_value(self) -> Optional[Date]:
        if self.rhs_ref is not None:
            if isinstance(self.rhs_ref, Date):
                return self.rhs_ref
            elif hasattr(self.rhs_ref, 'get_value'):
                try:
                    return self.rhs_ref.get_value()
                except ValueError:
                    return None
        return None

    # ★ prevent accidental boolean usage like: if (x == y): ...
    def __bool__(self):
        raise TypeError(
            "Constraint objects are not truthy. Add them to the solver via add_constraint()."
        )


# Module-level wrapper functions for Z3 boolean operators that work with ConstraintWrapper objects
def _wrap_constraint_for_enumeration(constraint: Any) -> ConstraintWrapper:
    """Wrap a constraint in ConstraintWrapper if it's not already wrapped."""
    if isinstance(constraint, ConstraintWrapper):
        return constraint
    elif isinstance(constraint, bool):
        return ConstraintWrapper(lambda: constraint)
    elif callable(constraint):
        return ConstraintWrapper(constraint)
    else:
        # Try to convert to bool
        return ConstraintWrapper(lambda: bool(constraint))


def Or_enumeration(*args) -> ConstraintWrapper:
    """Wrapper for Z3's Or() that works with enumeration baseline ConstraintWrapper objects."""
    wrapped_args = [_wrap_constraint_for_enumeration(arg) for arg in args]
    return ConstraintWrapper(
        func=lambda: any(c.evaluate() for c in wrapped_args),
        or_constraints=wrapped_args
    )


def And_enumeration(*args) -> ConstraintWrapper:
    """Wrapper for Z3's And() that works with enumeration baseline ConstraintWrapper objects."""
    wrapped_args = [_wrap_constraint_for_enumeration(arg) for arg in args]
    return ConstraintWrapper(
        func=lambda: all(c.evaluate() for c in wrapped_args)
    )


def Not_enumeration(arg) -> ConstraintWrapper:
    """Wrapper for Z3's Not() that works with enumeration baseline ConstraintWrapper objects."""
    wrapped_arg = _wrap_constraint_for_enumeration(arg)
    return ConstraintWrapper(
        func=lambda: not wrapped_arg.evaluate()
    )


def Implies_enumeration(antecedent, consequent) -> ConstraintWrapper:
    """Wrapper for Z3's Implies() that works with enumeration baseline ConstraintWrapper objects."""
    wrapped_antecedent = _wrap_constraint_for_enumeration(antecedent)
    wrapped_consequent = _wrap_constraint_for_enumeration(consequent)
    return ConstraintWrapper(
        func=lambda: not wrapped_antecedent.evaluate() or wrapped_consequent.evaluate()
    )


class EnumerationDateVar:
    """Date variable for enumeration baseline that evaluates constraints concretely."""

    def __init__(self, name: str, year: int = None, month: int = None, day: int = None):
        self.name = name
        self._year = year
        self._month = month
        self._day = day
        self._value = None
        if year is not None and month is not None and day is not None:
            self._value = Date(year, month, day)

    def __str__(self) -> str:
        return f"EnumerationDateVar({self.name})"

    def _hard_reset_value(self) -> None:
        """★ Reset cached concrete value for lazy nodes safely."""
        self._value = None
        # do NOT blindly clear year/month/day for base variables; only lazy nodes call this

    def set_value(self, year: int, month: int, day: int) -> None:
        self._year = year
        self._month = month
        self._day = day
        try:
            self._value = Date(year, month, day)
        except ValueError:
            self._value = None

    def clear_value(self) -> None:
        """Clear the concrete value without raising."""
        self._value = None
        # keep _year/_month/_day as-is; they are advisory, value drives truth

    def get_value(self) -> Optional[Date]:
        # Handle lazy operations
        if self._value is None and hasattr(self, '_lazy_op'):
            op_type, left, right = self._lazy_op
            # Evaluate left first (this recursively handles nested lazy operations)
            left_val = left.get_value()
            if left_val is None:
                return None
            # Apply the operation to the left value
            py_date = left_val.to_python_date()
            if op_type == 'add':
                    result_date = py_date + relativedelta(
                        years=right.years, months=right.months, days=right.days
                    )
            elif op_type == 'sub':
                    neg_period = Period(-right.years, -right.months, -right.days)
                    result_date = py_date + relativedelta(
                        years=neg_period.years, months=neg_period.months, days=neg_period.days
                    )
            else:  # defensive
                return None
            try:
                    result = Date.from_python_date(result_date)
                    self.set_value(result.year, result.month, result.day)
            except ValueError:
                # Date outside allowed range - return None instead of raising
                # This allows the solver to properly return UNSAT
                return None
        return self._value

    def to_concrete_date(self) -> Date:
        if self._value is None:
            raise ValueError(f"Date variable {self.name} has no concrete value")
        return self._value

    def _get_comparison_func(self, op: str, other: Union[Date, "EnumerationDateVar"]):
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
                return getattr(self_val.to_python_date(), f"__{op}__")(other_val.to_python_date())

            return compare
        else:
            raise TypeError(f"Cannot compare EnumerationDateVar with {type(other)}")

    def _get_equality_binding(self, other: Union[Date, "EnumerationDateVar"]) -> Optional[Date]:
        if isinstance(other, Date):
            return other
        elif isinstance(other, EnumerationDateVar):
            return other.get_value()  # may be None now; will be propagated later
        return None

    def __ge__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        return ConstraintWrapper(self._get_comparison_func("ge", other), var_ref=self, rhs_ref=other)

    def __le__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        return ConstraintWrapper(self._get_comparison_func("le", other), var_ref=self, rhs_ref=other)

    def __lt__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        return ConstraintWrapper(self._get_comparison_func("lt", other), var_ref=self, rhs_ref=other)

    def __gt__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:
        return ConstraintWrapper(self._get_comparison_func("gt", other), var_ref=self, rhs_ref=other)

    def __eq__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:  # type: ignore[override]
        concrete_value = self._get_equality_binding(other)
        return ConstraintWrapper(
            self._get_comparison_func("eq", other),
            var_ref=self,
            concrete_value=concrete_value,
            rhs_ref=other,
        )

    def __ne__(self, other: Union[Date, "EnumerationDateVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return ConstraintWrapper(self._get_comparison_func("ne", other), var_ref=self, rhs_ref=other)

    def __add__(self, other: Period) -> "EnumerationDateVar":
        if not isinstance(other, Period):
            raise TypeError(f"Cannot add {type(other)} to EnumerationDateVar")
        result_var = EnumerationDateVar(
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

    def __sub__(self, other: Period) -> "EnumerationDateVar":
        if not isinstance(other, Period):
            raise TypeError(f"Cannot subtract {type(other)} from EnumerationDateVar")
        result_var = EnumerationDateVar(
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


class EnumerationSolver:
    """Solver that enumerates all valid dates and checks constraints."""

    MIN_DATE = date(1900, 3, 1)
    MAX_DATE = date(2100, 2, 28)

    def __init__(self, timeout_ms: int = 600000):
        self.date_vars: Dict[str, EnumerationDateVar] = {}
        self.constraints: List[Any] = []
        self.timeout_ms = timeout_ms
        self._cached_valid_dates: Optional[List[date]] = None

    def add_date_var(self, name: str, year: int = None, month: int = None, day: int = None) -> EnumerationDateVar:
        if name not in self.date_vars:
            if year is not None and month is not None and day is not None:
                date_var = EnumerationDateVar(name, year, month, day)
            else:
                date_var = EnumerationDateVar(name)
            self.date_vars[name] = date_var
        elif year is not None and month is not None and day is not None:
            self.date_vars[name].set_value(year, month, day)
        return self.date_vars[name]

    def add_constraint(self, constraint: Any) -> None:
        self.constraints.append(constraint)
    
    def Or(self, *args) -> ConstraintWrapper:
        """Wrapper for Z3's Or() that creates a ConstraintWrapper with or_constraints."""
        return Or_enumeration(*args)
    
    def And(self, *args) -> ConstraintWrapper:
        """Wrapper for Z3's And() that creates a ConstraintWrapper."""
        return And_enumeration(*args)
    
    def Not(self, arg) -> ConstraintWrapper:
        """Wrapper for Z3's Not() that creates a ConstraintWrapper."""
        return Not_enumeration(arg)
    
    def Implies(self, antecedent, consequent) -> ConstraintWrapper:
        """Wrapper for Z3's Implies() that creates a ConstraintWrapper."""
        return Implies_enumeration(antecedent, consequent)
    
    def get_execution_context(self) -> Dict[str, Any]:
        """Get execution context dictionary for running generated constraint code.
        
        This sets up Or, And, Not, Implies to use the enumeration baseline's
        wrapper functions instead of Z3's functions, so boolean operators work
        correctly with ConstraintWrapper objects.
        
        Returns:
            Dictionary suitable for use as exec_globals when executing generated code
        """
        import builtins
        from .core import Date, Period
        
        # Create a mock z3 module with our wrapper functions
        class MockZ3:
            Or = self.Or
            And = self.And
            Not = self.Not
            Implies = self.Implies
            Int = lambda *args: None  # Not used by enumeration baseline
            Bool = lambda *args: None  # Not used by enumeration baseline
        
        # Override __import__ to return our mock z3 module
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'z3':
                return MockZ3()
            return original_import(name, *args, **kwargs)
        
        return {
            'Date': Date,
            'Period': Period,
            'DateSMTBuilder': lambda: self,
            'builder': self,
            'result': self,
            '__builtins__': {**builtins.__dict__, '__import__': mock_import},
        }

    def check(self) -> str:
        try:
            solution = self._find_solution()
            return 'sat' if solution is not None else 'unsat'
        except TimeoutError:
            return 'timeout'  # ★ cleaner status

    def solve(self) -> Dict[str, Any]:
        try:
            solution = self._find_solution()
            if solution is not None:
                return {'status': 'sat', 'dates': solution}
            else:
                return {'status': 'unsat', 'dates': {}}
        except TimeoutError as e:
            return {'status': 'timeout', 'reason': str(e), 'dates': {}}

    def model(self) -> Dict[str, Any]:
        out = self.solve()
        return out

    def get_concrete_dates(self) -> Dict[str, Date]:
        out = self.solve()
        return out.get('dates', {})

    def to_smt2(self) -> str:
        return "; Enumeration baseline - no SMT-LIB output"

    def get_assertions(self) -> list:
        return self.constraints

    def validate_solution(self, solution: Dict[str, Date]) -> bool:
        return self._evaluate_constraints(solution)

    # ------------------------- internals -------------------------

    def _find_solution(self) -> Optional[Dict[str, Date]]:
        """Brute-force enumeration: enumerate all possible dates for all variables.
        
        Pure enumeration baseline - no optimizations. Enumerates all combinations
        of dates for all base variables and checks which satisfy the constraints.
        
        If no variables are declared, evaluate constraints concretely using datetime.
        Otherwise, enumerate all possible date combinations for all declared variables.
        """
        var_names = list(self.date_vars.keys())

        # If no variables, evaluate constraints concretely using datetime
        if not var_names:
            return {} if self._evaluate_constraints({}) else None

        # Ensure any referenced vars exist (for intermediate lazy nodes)
        for c in self.constraints:
            if isinstance(c, ConstraintWrapper):
                if c.var_ref is not None and c.var_ref.name not in self.date_vars:
                    self.date_vars[c.var_ref.name] = c.var_ref
                if c.rhs_ref is not None and isinstance(c.rhs_ref, EnumerationDateVar):
                    if c.rhs_ref.name not in self.date_vars:
                        self.date_vars[c.rhs_ref.name] = c.rhs_ref

        # Get all base variables (skip intermediate lazy nodes)
        # NO BINDING OPTIMIZATION - enumerate all base variables
        base_vars: List[str] = []
        for name in list(self.date_vars.keys()):
            var = self.date_vars[name]
            # skip intermediate lazy nodes (they have _lazy_op attribute)
            if hasattr(var, '_lazy_op'):
                continue
            base_vars.append(name)

        if not base_vars:
            # No base variables to enumerate - evaluate constraints with empty assignment
            return {} if self._evaluate_constraints({}) else None

        # Generate all valid dates for each variable (full range)
        all_valid_dates = self._generate_all_valid_dates()
        
        # Build candidate lists: all valid dates for each variable
        candidate_lists = [all_valid_dates for _ in base_vars]

        # Quick product-size warning
        space = len(all_valid_dates) ** len(base_vars)
        if space > 1_000_000:
            print(f"Warning: Large search space ({space} combinations).")

        start = time.time()
        timeout_s = self.timeout_ms / 1000.0

        # Enumerate all combinations - pure brute force
        from itertools import product
        for combo in product(*candidate_lists):
            if (time.time() - start) > timeout_s:
                raise TimeoutError(
                    f"Enumeration timeout after {time.time() - start:.2f}s (limit: {timeout_s:.2f}s)"
                )

            # Create assignment: map each variable to a date
            assignment: Dict[str, Date] = {}
            for vname, dpy in zip(base_vars, combo):
                assignment[vname] = Date(dpy.year, dpy.month, dpy.day)
                self.date_vars[vname].set_value(dpy.year, dpy.month, dpy.day)

            # Evaluate constraints with this assignment
            if self._evaluate_constraints(assignment):
                return assignment

        return None


    def _generate_all_valid_dates(self) -> List[date]:
        if self._cached_valid_dates is None:
            dates: List[date] = []
            current = self.MIN_DATE
            while current <= self.MAX_DATE:
                try:
                    Date(current.year, current.month, current.day)
                    dates.append(current)
                except ValueError:
                    pass
                current += timedelta(days=1)
            self._cached_valid_dates = dates
        return self._cached_valid_dates

    def _evaluate_constraints(self, assignment: Dict[str, Date]) -> bool:
        try:
            # Make sure all referenced vars exist
            for c in self.constraints:
                if isinstance(c, ConstraintWrapper):
                    # Handle OR constraints - check all sub-constraints
                    if c.or_constraints is not None:
                        for sub_c in c.or_constraints:
                            if sub_c.var_ref is not None and sub_c.var_ref.name not in self.date_vars:
                                self.date_vars[sub_c.var_ref.name] = sub_c.var_ref
                            if sub_c.rhs_ref is not None and isinstance(sub_c.rhs_ref, EnumerationDateVar):
                                if sub_c.rhs_ref.name not in self.date_vars:
                                    self.date_vars[sub_c.rhs_ref.name] = sub_c.rhs_ref
                    else:
                        if c.var_ref is not None and c.var_ref.name not in self.date_vars:
                            self.date_vars[c.var_ref.name] = c.var_ref
                        if c.rhs_ref is not None and isinstance(c.rhs_ref, EnumerationDateVar):
                            if c.rhs_ref.name not in self.date_vars:
                                self.date_vars[c.rhs_ref.name] = c.rhs_ref

            # Reset lazy nodes so they recompute from base values
            for name, var in list(self.date_vars.items()):
                if hasattr(var, '_lazy_op'):
                    var._hard_reset_value()  # ★

            # Set all base variable values for this assignment
            for name, d in assignment.items():
                if name in self.date_vars:
                    self.date_vars[name].set_value(d.year, d.month, d.day)

            # Evaluate
            for c in self.constraints:
                if isinstance(c, bool):
                    if not c:
                        return False
                elif isinstance(c, ConstraintWrapper):
                    if not c.evaluate():
                        return False
                elif callable(c):
                    if not c():
                        return False
                else:
                    # last resort: bool() — but many types (like ConstraintWrapper) forbid __bool__
                    if not bool(c):
                            return False
            return True
        except (ValueError, TypeError):
            return False
