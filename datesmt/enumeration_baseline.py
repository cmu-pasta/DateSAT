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

    def __init__(self, func, description: str = "", var_ref=None, concrete_value=None, rhs_ref=None, or_constraints=None):
        self.func = func
        self.description = description
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
        return self.concrete_value is not None and self.var_ref is not None

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
            left_val = left.get_value()
            if left_val is None:
                return None
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

    def add_constraint(self, constraint: Any, description: str = "") -> None:
        self.constraints.append(constraint)

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

        # Automatically bind variables that are assigned to a concrete Date
        # and substitute them in all constraints
        bound_assignments: Dict[str, Date] = {}
        changed = True
        while changed:
            changed = False
            for c in self.constraints:
                if not isinstance(c, ConstraintWrapper):
                    continue
                if not c.is_equality_binding():
                    continue
                if c.var_ref is None:
                    continue

                name = c.var_ref.name
                # Skip if already bound
                if name in bound_assignments:
                    continue

                value = c.concrete_value
                if value is None:
                    # Try to evaluate RHS - if it references bound variables, substitute them
                    if c.rhs_ref is not None:
                        if isinstance(c.rhs_ref, Date):
                            value = c.rhs_ref
                        elif isinstance(c.rhs_ref, EnumerationDateVar):
                            # If RHS is a bound variable, use its concrete date
                            if c.rhs_ref.name in bound_assignments:
                                value = bound_assignments[c.rhs_ref.name]
                            else:
                                # Check if it's a lazy operation (x + P or x - P) that can be evaluated
                                if hasattr(c.rhs_ref, '_lazy_op'):
                                    op_type, left, right = c.rhs_ref._lazy_op
                                    if isinstance(left, EnumerationDateVar) and left.name in bound_assignments:
                                        # Evaluate the lazy operation with the bound variable
                                        left_date = bound_assignments[left.name]
                                        py_date = left_date.to_python_date()
                                        if op_type == 'add':
                                            result_date = py_date + relativedelta(
                                                years=right.years, months=right.months, days=right.days
                                            )
                                        elif op_type == 'sub':
                                            result_date = py_date + relativedelta(
                                                years=-right.years, months=-right.months, days=-right.days
                                            )
                                        else:
                                            result_date = None
                                        if result_date is not None:
                                            try:
                                                value = Date.from_python_date(result_date)
                                            except ValueError:
                                                pass
                                # If still None, try get_value() - this should work if x is bound
                                if value is None:
                                    val = c.rhs_ref.get_value()
                                    if val is not None:
                                        value = val

                if isinstance(value, Date):
                    bound_assignments[name] = value
                    if name not in self.date_vars:
                        self.date_vars[name] = c.var_ref
                    self.date_vars[name].set_value(value.year, value.month, value.day)
                    changed = True

        # Get all base variables (skip intermediate lazy nodes)
        base_vars: List[str] = []
        for name in list(self.date_vars.keys()):
            # skip intermediate lazy nodes
            if '_plus_' in name or '_minus_' in name:
                continue
            if name in bound_assignments:
                continue
            base_vars.append(name)

        if not base_vars:
            assignment = dict(bound_assignments)
            return assignment if self._evaluate_constraints(assignment) else None

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

        # Enumerate all combinations
        from itertools import product
        for combo in product(*candidate_lists):
            if (time.time() - start) > timeout_s:
                raise TimeoutError(
                    f"Enumeration timeout after {time.time() - start:.2f}s (limit: {timeout_s:.2f}s)"
                )

            # Create assignment: map each variable to a date
            assignment: Dict[str, Date] = dict(bound_assignments)
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
                if '_plus_' in name or '_minus_' in name:
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
