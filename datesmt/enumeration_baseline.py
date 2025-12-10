"""
Enumeration baseline implementation for comparison with DATE-SMT.

This module provides a baseline solver that enumerates all valid dates
in the allowed range [1900-03-01 to 2100-02-28] for date variables and
checks which assignments satisfy the constraints. 
This is a brute-force approach that guarantees
finding a solution if one exists, but may be very slow.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, Optional, Union, List, Tuple
import time
from .core import Date, Period
import itertools
import builtins


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

    # ★ prevent accidental boolean usage like: if (x == y): ...
    def __bool__(self):
        raise TypeError(
            "Constraint objects are not truthy. Add them to the solver via add_constraint()."
        )


class EnumerationComponentVar:
    """Symbolic date component variable (year, month, or day) for use inside Date() constructor."""
    
    def __init__(self, name: str, min_val: int, max_val: int, component_type: str):
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.component_type = component_type  # 'year', 'month', or 'day'
        self._value = None
    
    def set_value(self, val: int) -> None:
        if self.min_val <= val <= self.max_val:
            self._value = val
        else:
            raise ValueError(f"{self.component_type} value {val} out of range [{self.min_val}, {self.max_val}]")
    
    def get_value(self) -> Optional[int]:
        return self._value
    
    def clear_value(self) -> None:
        self._value = None
    
    def __str__(self) -> str:
        return f"EnumerationComponentVar({self.name}, {self.component_type})"
    
    # Arithmetic operations for expressions like year_var + 1
    def __add__(self, other: int) -> "EnumerationComponentExpr":
        if not isinstance(other, int):
            raise TypeError(f"Cannot add {type(other)} to EnumerationComponentVar")
        return EnumerationComponentExpr(self, 'add', other)
    
    def __sub__(self, other: int) -> "EnumerationComponentExpr":
        if not isinstance(other, int):
            raise TypeError(f"Cannot subtract {type(other)} from EnumerationComponentVar")
        return EnumerationComponentExpr(self, 'sub', other)

    def __mul__(self, other: int) -> "EnumerationComponentExpr":
        if not isinstance(other, int):
            raise TypeError(f"Cannot multiply {type(other)} by EnumerationComponentVar")
        return EnumerationComponentExpr(self, 'mul', other)


class EnumerationComponentExpr:
    """Expression involving a component variable and a constant (e.g., year_var + 1)."""
    
    def __init__(self, var: EnumerationComponentVar, op: str, constant: int):
        self.var = var
        self.op = op
        self.constant = constant
    
    def evaluate(self) -> Optional[int]:
        val = self.var.get_value()
        if val is None:
            return None
        if self.op == 'add':
            return val + self.constant
        elif self.op == 'sub':
            return val - self.constant
        elif self.op == 'mul':
            return val * self.constant
        return None
    
    def get_base_var(self) -> EnumerationComponentVar:
        return self.var


class EnumerationDateVar:
    """Date variable for enumeration baseline that evaluates constraints concretely."""

    def __init__(self, name: str):
        self.name = name
        self._year = None
        self._month = None
        self._day = None
        self._value = None

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

    # Expose year/month/day components for constraint building (date-only support)
    @property
    def year(self) -> "EnumerationDateComponent":
        return EnumerationDateComponent(self, "year")

    @property
    def month(self) -> "EnumerationDateComponent":
        return EnumerationDateComponent(self, "month")

    @property
    def day(self) -> "EnumerationDateComponent":
        return EnumerationDateComponent(self, "day")


class EnumerationDateComponent:
    """Int-like view for a date component (year/month/day) used only in date constraints."""

    def __init__(self, parent: EnumerationDateVar, attr: str):
        self.parent = parent
        self.attr = attr

    def _compare(self, op: str, other: int):
        def compare():
            d = self.parent.get_value()
            if d is None:
                return False
            lhs = getattr(d, self.attr)
            return getattr(lhs, f"__{op}__")(other)

        return compare

    def __eq__(self, other: int) -> ConstraintWrapper:  # type: ignore[override]
        return ConstraintWrapper(self._compare("eq", int(other)))

    def __ne__(self, other: int) -> ConstraintWrapper:  # type: ignore[override]
        return ConstraintWrapper(self._compare("ne", int(other)))

    def __lt__(self, other: int) -> ConstraintWrapper:
        return ConstraintWrapper(self._compare("lt", int(other)))

    def __le__(self, other: int) -> ConstraintWrapper:
        return ConstraintWrapper(self._compare("le", int(other)))

    def __gt__(self, other: int) -> ConstraintWrapper:
        return ConstraintWrapper(self._compare("gt", int(other)))

    def __ge__(self, other: int) -> ConstraintWrapper:
        return ConstraintWrapper(self._compare("ge", int(other)))


class EnumerationSolver:
    """Solver that enumerates all valid dates and checks constraints."""

    MIN_DATE = date(1900, 3, 1)
    MAX_DATE = date(2100, 2, 28)

    def __init__(self, timeout_ms: int = 60000):
        self.date_vars: Dict[str, EnumerationDateVar] = {}
        self.component_vars: Dict[str, EnumerationComponentVar] = {}  # Component variables - e.x. Date(y, 1, 1)
        self.constraints: List[Any] = []
        self.timeout_ms = timeout_ms
        self._cached_valid_dates: Optional[List[date]] = None

    def add_date_var(self, name: str) -> EnumerationDateVar:
        """Declare a new symbolic date variable.
        
        The variable will enumerate all valid dates in the allowed range.
        
        Args:
            name: Variable name (must be unique)
        
        Returns:
            The created EnumerationDateVar
        
        Raises:
            ValueError: If a variable with this name already exists
        """
        if name in self.date_vars:
            raise ValueError(f"Date variable '{name}' already declared")
        
        date_var = EnumerationDateVar(name)
        self.date_vars[name] = date_var
        return date_var
    
    def add_year_var(self, name: str) -> EnumerationComponentVar:
        """Declare a symbolic year variable that enumerates from 1900 to 2100.
        
        Raises:
            ValueError: If a component variable with this name already exists
        """
        if name in self.component_vars:
            raise ValueError(f"Component variable '{name}' already declared")
        
        var = EnumerationComponentVar(name, 1900, 2100, 'year')
        self.component_vars[name] = var
        return var
    
    def add_month_var(self, name: str) -> EnumerationComponentVar:
        """Declare a symbolic month variable that enumerates from 1 to 12.
        
        Raises:
            ValueError: If a component variable with this name already exists
        """
        if name in self.component_vars:
            raise ValueError(f"Component variable '{name}' already declared")
        
        var = EnumerationComponentVar(name, 1, 12, 'month')
        self.component_vars[name] = var
        return var
    
    def add_day_var(self, name: str) -> EnumerationComponentVar:
        """Declare a symbolic day variable that enumerates from 1 to 31.
        
        Raises:
            ValueError: If a component variable with this name already exists
        """
        if name in self.component_vars:
            raise ValueError(f"Component variable '{name}' already declared")
        
        var = EnumerationComponentVar(name, 1, 31, 'day')
        self.component_vars[name] = var
        return var
    
    def SymbolicDate(self, year, month, day) -> EnumerationDateVar:
        """Create a date with symbolic components.
        
        Args:
            year: int, EnumerationComponentVar, or EnumerationComponentExpr
            month: int, EnumerationComponentVar, or EnumerationComponentExpr
            day: int, EnumerationComponentVar, or EnumerationComponentExpr
        
        Returns:
            EnumerationDateVar that will be enumerated based on symbolic components
        
        Example:
            year_var = solver.add_year_var("y")
            d = solver.SymbolicDate(year_var, 1, 1)  # Only enumerates years
            solver.add_constraint(x < d)
        """
        # Generate a unique name for this symbolic date
        symbolic_parts = []
        if isinstance(year, (EnumerationComponentVar, EnumerationComponentExpr)):
            symbolic_parts.append('y')
        if isinstance(month, (EnumerationComponentVar, EnumerationComponentExpr)):
            symbolic_parts.append('m')
        if isinstance(day, (EnumerationComponentVar, EnumerationComponentExpr)):
            symbolic_parts.append('d')
        
        name = f"symdate_{''.join(symbolic_parts)}_{len(self.date_vars)}"
        date_var = EnumerationDateVar(name)
        
        # Store component specifications (can be int, EnumerationComponentVar, or EnumerationComponentExpr)
        date_var._year_spec = year
        date_var._month_spec = month
        date_var._day_spec = day
        
        self.date_vars[name] = date_var
        return date_var

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
        # Create a mock z3 module with our wrapper functions
        class MockZ3:
            Or = self.Or
            And = self.And
            Not = self.Not
            Implies = self.Implies
            Int = lambda *args: None  # Not used by enumeration baseline solving
            Bool = lambda *args: None  # Not used by enumeration baseline solving
        
        # Override __import__ to return our mock z3 module
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'z3':
                return MockZ3()
            return original_import(name, *args, **kwargs)
        
        return {
            'Date': Date,
            'Period': Period,
            'SymbolicDate': self.SymbolicDate,
            'DateSMTBuilder': lambda: self,
            'builder': self,
            'result': self,
            '__builtins__': {**builtins.__dict__, '__import__': mock_import},
            'And': self.And,
            'Or': self.Or,
            'Not': self.Not,
            'Implies': self.Implies,
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

    # ------------------------- internals -------------------------

    def _find_solution(self) -> Optional[Dict[str, Date]]:
        """Brute-force enumeration: enumerate all possible dates for all variables.
        
        Pure enumeration baseline - no optimizations. Enumerates all combinations
        of dates for all base variables and checks which satisfy the constraints.
        
        Supports both full date variables and dates with symbolic components.
        For dates with symbolic components (e.g., Date(year_var, 1, 1)), only
        the symbolic components are enumerated, making it much more efficient.
        
        If no variables are declared, evaluate constraints concretely using datetime.
        Otherwise, enumerate all possible date combinations for all declared variables.
        """
        var_names = list(self.date_vars.keys())

        # If no variables, evaluate constraints concretely using datetime
        if not var_names:
            return {} if self._evaluate_constraints({}) else None

        # Register intermediate lazy nodes (created by operations like x + Period)
        # These are derived variables, not base variables
        for c in self.constraints:
            if isinstance(c, ConstraintWrapper):
                targets = c.or_constraints if c.or_constraints is not None else [c]
                for sub_c in targets:
                    # Only register lazy nodes (have _lazy_op), not undeclared base variables
                    if sub_c.var_ref is not None and isinstance(sub_c.var_ref, EnumerationDateVar):
                        if hasattr(sub_c.var_ref, '_lazy_op') and sub_c.var_ref.name not in self.date_vars:
                            self.date_vars[sub_c.var_ref.name] = sub_c.var_ref
                    if sub_c.rhs_ref is not None and isinstance(sub_c.rhs_ref, EnumerationDateVar):
                        if hasattr(sub_c.rhs_ref, '_lazy_op') and sub_c.rhs_ref.name not in self.date_vars:
                            self.date_vars[sub_c.rhs_ref.name] = sub_c.rhs_ref

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

        # Build candidate lists for each variable
        # Variables with symbolic components get specialized enumeration
        candidate_lists = []
        for vname in base_vars:
            var = self.date_vars[vname]
            candidates = self._generate_candidates_for_var(var)
            candidate_lists.append(candidates)

        # Calculate search space
        space = 1
        for candidates in candidate_lists:
            space *= len(candidates)
        if space > 1_000_000:
            print(f"Warning: Large search space ({space} combinations).")

        start = time.time()
        timeout_s = self.timeout_ms / 1000.0

        # Enumerate all combinations - pure brute force
        for combo in itertools.product(*candidate_lists):
            if (time.time() - start) > timeout_s:
                raise TimeoutError(
                    f"Enumeration timeout after {time.time() - start:.2f}s (limit: {timeout_s:.2f}s)"
                )

            # Create assignment: map each variable to a date
            assignment: Dict[str, Date] = {}
            valid_assignment = True
            
            for vname, candidate in zip(base_vars, combo):
                var = self.date_vars[vname]
                
                # Handle symbolic component dates
                if hasattr(var, '_year_spec'):
                    # Check if any component is symbolic
                    has_symbolic = (isinstance(var._year_spec, (EnumerationComponentVar, EnumerationComponentExpr)) or
                                  isinstance(var._month_spec, (EnumerationComponentVar, EnumerationComponentExpr)) or
                                  isinstance(var._day_spec, (EnumerationComponentVar, EnumerationComponentExpr)))
                    
                    if has_symbolic:
                        # candidate is a tuple (year, month, day, base_year, base_month, base_day)
                        # The base values are for setting the component variables
                        year, month, day, base_year, base_month, base_day = candidate
                        # Set component variable values (use base values, not expression results)
                        if isinstance(var._year_spec, (EnumerationComponentVar, EnumerationComponentExpr)):
                            base_var = self._get_base_component_var(var._year_spec)
                            if base_var:
                                base_var.set_value(base_year)
                        if isinstance(var._month_spec, (EnumerationComponentVar, EnumerationComponentExpr)):
                            base_var = self._get_base_component_var(var._month_spec)
                            if base_var:
                                base_var.set_value(base_month)
                        if isinstance(var._day_spec, (EnumerationComponentVar, EnumerationComponentExpr)):
                            base_var = self._get_base_component_var(var._day_spec)
                            if base_var:
                                base_var.set_value(base_day)
                        
                        try:
                            date_obj = Date(year, month, day)
                            assignment[vname] = date_obj
                            var.set_value(year, month, day)
                        except ValueError:
                            # Invalid date (e.g., Feb 31), skip this combination
                            valid_assignment = False
                            break
                    else:
                        # SymbolicDate but no symbolic components - shouldn't happen
                        # Regular date variable - candidate is already a python date
                        assignment[vname] = Date(candidate.year, candidate.month, candidate.day)
                        var.set_value(candidate.year, candidate.month, candidate.day)
                else:
                    # Regular date variable - candidate is already a python date
                    assignment[vname] = Date(candidate.year, candidate.month, candidate.day)
                    var.set_value(candidate.year, candidate.month, candidate.day)
            
            if not valid_assignment:
                continue

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
    
    def _get_base_component_var(self, component) -> Optional[EnumerationComponentVar]:
        """Get the base component variable from a component (handles expressions too)."""
        if isinstance(component, EnumerationComponentVar):
            return component
        elif isinstance(component, EnumerationComponentExpr):
            return component.get_base_var()
        return None
    
    def _evaluate_component(self, component) -> Optional[int]:
        """Evaluate a component to get its integer value."""
        if isinstance(component, int):
            return component
        elif isinstance(component, EnumerationComponentVar):
            return component.get_value()
        elif isinstance(component, EnumerationComponentExpr):
            return component.evaluate()
        return None
    
    def _generate_candidates_for_var(self, var: EnumerationDateVar) -> List[Union[date, Tuple[int, int, int, int, int, int]]]:
        """Generate candidate values for a variable.
        
        For regular date variables, returns list of python dates.
        For symbolic component dates, returns list of (year, month, day, base_year, base_month, base_day) tuples.
        The base values are what the underlying component variables should be set to.
        """
        # Check if this is a symbolic component date
        if not hasattr(var, '_year_spec'):
            # Regular date variable - enumerate all valid dates
            return self._generate_all_valid_dates()
        
        # Check if any component is symbolic
        has_symbolic = (isinstance(var._year_spec, (EnumerationComponentVar, EnumerationComponentExpr)) or
                       isinstance(var._month_spec, (EnumerationComponentVar, EnumerationComponentExpr)) or
                       isinstance(var._day_spec, (EnumerationComponentVar, EnumerationComponentExpr)))
        
        if not has_symbolic:
            # SymbolicDate but no symbolic components - shouldn't happen
            return self._generate_all_valid_dates()
        
        # Symbolic component date - enumerate only symbolic components
        year_ranges = self._get_component_ranges(var._year_spec, 'year')
        month_ranges = self._get_component_ranges(var._month_spec, 'month')
        day_ranges = self._get_component_ranges(var._day_spec, 'day')
        
        # Generate all combinations of (year, month, day, base_year, base_month, base_day)
        # Note: We don't validate here, validation happens during enumeration
        # This allows us to skip invalid dates like Feb 31
        candidates = []
        for y_tuple in year_ranges:
            for m_tuple in month_ranges:
                for d_tuple in day_ranges:
                    y_val, y_base = y_tuple
                    m_val, m_base = m_tuple
                    d_val, d_base = d_tuple
                    candidates.append((y_val, m_val, d_val, y_base, m_base, d_base))
        
        return candidates
    
    def _get_component_ranges(self, component_spec, component_type: str) -> List[Tuple[int, int]]:
        """Get the range of values for a date component.
        
        Args:
            component_spec: int, EnumerationComponentVar, or EnumerationComponentExpr
            component_type: 'year', 'month', or 'day' (for fallback ranges)
        
        Returns list of (evaluated_value, base_value) tuples.
        - evaluated_value: the actual value to use in the Date() constructor
        - base_value: the value to set in the underlying EnumerationComponentVar
        """
        if isinstance(component_spec, (EnumerationComponentVar, EnumerationComponentExpr)):
            # Symbolic component - get base variable and enumerate its range
            base_var = self._get_base_component_var(component_spec)
            if base_var:
                base_range = range(base_var.min_val, base_var.max_val + 1)
                
                if isinstance(component_spec, EnumerationComponentExpr):
                    # For expressions like year_var + 1, enumerate base variable
                    # and compute the expression result
                    results = []
                    for base_val in base_range:
                        if component_spec.op == 'add':
                            eval_val = base_val + component_spec.constant
                        elif component_spec.op == 'sub':
                            eval_val = base_val - component_spec.constant
                        else:
                            eval_val = base_val
                        results.append((eval_val, base_val))
                    return results
                else:
                    # Simple variable, base value and evaluated value are the same
                    return [(v, v) for v in base_range]
        
        # Concrete component (int) - single value, no base variable
        if isinstance(component_spec, int):
            return [(component_spec, component_spec)]
        
        # Fallback - shouldn't happen but be safe
        if component_type == 'year':
            vals = list(range(1900, 2101))
        elif component_type == 'month':
            vals = list(range(1, 13))
        else:  # day
            vals = list(range(1, 32))
        return [(v, v) for v in vals]

    def _evaluate_constraints(self, assignment: Dict[str, Date]) -> bool:
        try:
            # Register intermediate lazy nodes for evaluation
            for c in self.constraints:
                if isinstance(c, ConstraintWrapper):
                    # Handle OR constraints - check all sub-constraints
                    targets = c.or_constraints if c.or_constraints is not None else [c]
                    for sub_c in targets:
                        # Only register lazy nodes, not undeclared base variables
                        if sub_c.var_ref is not None and isinstance(sub_c.var_ref, EnumerationDateVar):
                            if hasattr(sub_c.var_ref, '_lazy_op') and sub_c.var_ref.name not in self.date_vars:
                                self.date_vars[sub_c.var_ref.name] = sub_c.var_ref
                        if sub_c.rhs_ref is not None and isinstance(sub_c.rhs_ref, EnumerationDateVar):
                            if hasattr(sub_c.rhs_ref, '_lazy_op') and sub_c.rhs_ref.name not in self.date_vars:
                                self.date_vars[sub_c.rhs_ref.name] = sub_c.rhs_ref

            # Reset lazy nodes so they recompute from base values
            for _, var in list(self.date_vars.items()):
                if hasattr(var, '_lazy_op'):
                    var._hard_reset_value()  # ★

            # Set all base variable values for this assignment
            for name, val in assignment.items():
                if name in self.date_vars and isinstance(val, Date):
                    self.date_vars[name].set_value(val.year, val.month, val.day)

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
