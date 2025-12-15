"""
Pure-Python constraint validation for solved assignments.

This module executes generated constraint code using a lightweight builder that
supports date, int, and bool variables, and then evaluates all constraints
against a provided concrete solution (no solving capability).
"""

from typing import Any, Dict, Optional, Tuple, Union
from dateutil.relativedelta import relativedelta
import datetime

from .core import Date, Period
from .enumeration_baseline import (
    ConstraintWrapper,
    Or_enumeration,
    And_enumeration,
    Not_enumeration,
    Implies_enumeration,
)


class _UnboundedDate:
    """
    Wrapper for Python datetime that provides Date-like interface but without bounds checking.
    Used during validation when date arithmetic goes outside Date-SMT's supported range.
    """
    def __init__(self, py_date: datetime.date):
        self._py_date = py_date
        self.year = py_date.year
        self.month = py_date.month
        self.day = py_date.day
    
    def to_python_date(self) -> datetime.date:
        return self._py_date
    
    def __repr__(self) -> str:
        return f"Date({self.year}, {self.month}, {self.day})"
    
    def __str__(self) -> str:
        return f"Date({self.year}, {self.month}, {self.day})"


class EvalDateVar:
    def __init__(self, name: str):
        self.name = name
        self._value: Optional[Date] = None
        self._lazy_op = None  # ("add"|"sub", EvalDateVar, Period)

    def set_value(self, year: int, month: int, day: int) -> None:
        try:
            self._value = Date(year, month, day)
        except ValueError:
            self._value = None

    def clear_value(self) -> None:
        self._value = None

    def _hard_reset_value(self) -> None:
        self._value = None

    def get_value(self) -> Optional[Date]:
        if self._value is None and self._lazy_op is not None:
            op_type, left, period = self._lazy_op
            left_val = left.get_value()
            if left_val is None:
                return None
            py_date = left_val.to_python_date()
            delta = relativedelta(
                years=period.years, months=period.months, days=period.days
            )
            if op_type == "add":
                result_date = py_date + delta
            else:
                result_date = py_date - delta
            try:
                # Try to create a Date object (respects bounds)
                result = Date.from_python_date(result_date)
                self.set_value(result.year, result.month, result.day)
            except ValueError:
                # Date is out of Date-SMT bounds, but still valid for validation
                # Store as a pseudo-Date using a custom unbounded wrapper
                self._value = _UnboundedDate(result_date)
        return self._value

    # comparisons
    def _cmp(self, op: str, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        def compare():
            lhs = self.get_value()
            if lhs is None:
                return False
            rhs_val: Optional[Union[Date, _UnboundedDate]]
            if isinstance(other, (Date, _UnboundedDate)):
                rhs_val = other
            else:
                rhs_val = other.get_value()
            if rhs_val is None:
                return False
            return getattr(lhs.to_python_date(), f"__{op}__")(rhs_val.to_python_date())

        concrete_value = other if isinstance(other, (Date, _UnboundedDate)) else None
        return ConstraintWrapper(
            compare, var_ref=self, concrete_value=concrete_value, rhs_ref=other
        )

    def __eq__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("eq", other)

    def __ne__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("ne", other)

    def __lt__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        return self._cmp("lt", other)

    def __le__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        return self._cmp("le", other)

    def __gt__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        return self._cmp("gt", other)

    def __ge__(self, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        return self._cmp("ge", other)

    def __add__(self, other: Period) -> "EvalDateVar":
        if not isinstance(other, Period):
            raise TypeError("Can only add Period to DateVar")
        out = EvalDateVar(f"{self.name}_plus")
        out._lazy_op = ("add", self, other)
        return out

    def __sub__(self, other: Period) -> "EvalDateVar":
        if not isinstance(other, Period):
            raise TypeError("Can only subtract Period from DateVar")
        out = EvalDateVar(f"{self.name}_minus")
        out._lazy_op = ("sub", self, other)
        return out

    # year/month/day projections
    @property
    def year(self) -> "EvalDateComponent":
        return EvalDateComponent(self, "year")

    @property
    def month(self) -> "EvalDateComponent":
        return EvalDateComponent(self, "month")

    @property
    def day(self) -> "EvalDateComponent":
        return EvalDateComponent(self, "day")


class EvalDateComponent:
    def __init__(self, parent: EvalDateVar, attr: str):
        self.parent = parent
        self.attr = attr

    def _cmp(self, op: str, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        def compare():
            d = self.parent.get_value()
            if d is None:
                return False
            # Get the component value (works for both Date and _UnboundedDate)
            component_val = getattr(d, self.attr)
            # Handle EvalIntVar
            if isinstance(other, EvalIntVar):
                other_val = other.get_value()
                if other_val is None:
                    return False
                return getattr(component_val, f"__{op}__")(other_val)
            else:
                return getattr(component_val, f"__{op}__")(int(other))

        return ConstraintWrapper(compare)

    def __eq__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("eq", other)

    def __ne__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("ne", other)

    def __lt__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("lt", other)

    def __le__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("le", other)

    def __gt__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("gt", other)

    def __ge__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("ge", other)


class EvalIntVar:
    def __init__(self, name: str):
        self.name = name
        self._value: Optional[int] = None

    def set_value(self, v: int) -> None:
        try:
            self._value = int(v)
        except Exception:
            self._value = None

    def get_value(self) -> Optional[int]:
        return self._value

    def _cmp(self, op: str, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        def rhs():
            if isinstance(other, EvalIntVar):
                return other.get_value()
            try:
                return int(other)
            except Exception:
                return None

        def compare():
            lhs = self.get_value()
            rv = rhs()
            if lhs is None or rv is None:
                return False
            return getattr(lhs, f"__{op}__")(rv)

        return ConstraintWrapper(compare, var_ref=self, rhs_ref=other)

    def __eq__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("eq", other)

    def __ne__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("ne", other)

    def __lt__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("lt", other)

    def __le__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("le", other)

    def __gt__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("gt", other)

    def __ge__(self, other: Union[int, "EvalIntVar"]) -> ConstraintWrapper:
        return self._cmp("ge", other)

    def __add__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_plus")

        def compute():
            lhs = self.get_value()
            rv = other.get_value() if isinstance(other, EvalIntVar) else int(other)
            if lhs is None or rv is None:
                return None
            return lhs + rv

        out.get_value = compute  # type: ignore
        return out

    def __sub__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_minus")

        def compute():
            lhs = self.get_value()
            rv = other.get_value() if isinstance(other, EvalIntVar) else int(other)
            if lhs is None or rv is None:
                return None
            return lhs - rv

        out.get_value = compute  # type: ignore
        return out


class EvalBoolVar:
    def __init__(self, name: str):
        self.name = name
        self._value: Optional[bool] = None

    def set_value(self, v: Union[bool, str, int]) -> None:
        if isinstance(v, bool):
            self._value = v
            return
        if isinstance(v, str):
            lv = v.strip().lower()
            if lv in ("true", "1", "yes", "y", "t"):
                self._value = True
                return
            if lv in ("false", "0", "no", "n", "f"):
                self._value = False
                return
        try:
            self._value = bool(int(v))
        except Exception:
            self._value = None

    def get_value(self) -> Optional[bool]:
        return self._value

    def _cmp(self, op: str, other: Union[bool, "EvalBoolVar", ConstraintWrapper]) -> ConstraintWrapper:
        def rhs():
            if isinstance(other, EvalBoolVar):
                return other.get_value()
            if isinstance(other, bool):
                return other
            if isinstance(other, ConstraintWrapper):
                # Evaluate the constraint wrapper to get a boolean
                return other.evaluate()
            return None

        def compare():
            lhs = self.get_value()
            rv = rhs()
            if lhs is None or rv is None:
                return False
            return getattr(lhs, f"__{op}__")(rv)

        return ConstraintWrapper(compare, var_ref=self, rhs_ref=other)

    def __eq__(self, other: Union[bool, "EvalBoolVar", ConstraintWrapper]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("eq", other)

    def __ne__(self, other: Union[bool, "EvalBoolVar", ConstraintWrapper]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("ne", other)

    def __invert__(self) -> ConstraintWrapper:
        return ConstraintWrapper(lambda: not bool(self.get_value()))

    def __and__(self, other: Any) -> ConstraintWrapper:
        return And_enumeration(self, other)

    def __or__(self, other: Any) -> ConstraintWrapper:
        return Or_enumeration(self, other)


class EvalBuilder:
    """Lightweight builder used only for validation of a provided solution."""

    def __init__(self):
        self.date_vars: Dict[str, EvalDateVar] = {}
        self.int_vars: Dict[str, EvalIntVar] = {}
        self.bool_vars: Dict[str, EvalBoolVar] = {}
        self.constraints: list = []

    # variable builders
    def add_date_var(self, name: str) -> EvalDateVar:
        if name not in self.date_vars:
            self.date_vars[name] = EvalDateVar(name)
        return self.date_vars[name]

    def add_int_var(self, name: str) -> EvalIntVar:
        if name not in self.int_vars:
            self.int_vars[name] = EvalIntVar(name)
        return self.int_vars[name]

    def add_bool_var(self, name: str) -> EvalBoolVar:
        if name not in self.bool_vars:
            self.bool_vars[name] = EvalBoolVar(name)
        return self.bool_vars[name]

    # logical wrappers
    def Or(self, *args) -> ConstraintWrapper:
        return Or_enumeration(*args)

    def And(self, *args) -> ConstraintWrapper:
        return And_enumeration(*args)

    def Not(self, arg) -> ConstraintWrapper:
        return Not_enumeration(arg)

    def Implies(self, antecedent, consequent) -> ConstraintWrapper:
        return Implies_enumeration(antecedent, consequent)

    # constraint collector
    def add_constraint(self, constraint: Any) -> None:
        self.constraints.append(constraint)

    # context for exec
    def get_execution_context(self) -> Dict[str, Any]:
        import builtins

        class MockZ3:
            Or = staticmethod(lambda *args: Or_enumeration(*args))
            And = staticmethod(lambda *args: And_enumeration(*args))
            Not = staticmethod(lambda arg: Not_enumeration(arg))
            Implies = staticmethod(lambda a, c: Implies_enumeration(a, c))
            Int = staticmethod(lambda *args: None)
            Bool = staticmethod(lambda *args: None)

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "z3":
                return MockZ3()
            return original_import(name, *args, **kwargs)

        # Custom Date wrapper that handles EvalIntVar arguments
        def DateWrapper(year: Union[int, EvalIntVar], month: Union[int, EvalIntVar], day: Union[int, EvalIntVar]) -> Union[Date, EvalDateVar]:
            # If any argument is an EvalIntVar, we need to defer evaluation
            if isinstance(year, EvalIntVar) or isinstance(month, EvalIntVar) or isinstance(day, EvalIntVar):
                # Create a lazy EvalDateVar that will compute the date when needed
                lazy_date = EvalDateVar(f"date_literal")
                year_var = year
                month_var = month
                day_var = day
                
                def get_date_value():
                    y = year_var.get_value() if isinstance(year_var, EvalIntVar) else year_var
                    m = month_var.get_value() if isinstance(month_var, EvalIntVar) else month_var
                    d = day_var.get_value() if isinstance(day_var, EvalIntVar) else day_var
                    if y is None or m is None or d is None:
                        return None
                    try:
                        return Date(int(y), int(m), int(d))
                    except ValueError:
                        return None
                
                lazy_date.get_value = get_date_value  # type: ignore
                return lazy_date
            else:
                # All concrete values, can create Date immediately
                return Date(int(year), int(month), int(day))

        return {
            "Date": DateWrapper,
            "Period": Period,
            "DateSMTBuilder": lambda: self,
            "builder": self,
            "result": self,
            "__builtins__": {**builtins.__dict__, "__import__": mock_import},
            "And": self.And,
            "Or": self.Or,
            "Not": self.Not,
            "Implies": self.Implies,
        }


def _parse_date_string(date_str: str) -> Date:
    date_str = date_str.strip()
    if date_str.startswith("Date(") and date_str.endswith(")"):
        inner = date_str[len("Date(") : -1]
        parts = [p.strip() for p in inner.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Unrecognized Date format: {date_str}")
        y, m, d = map(int, parts)
        return Date(y, m, d)
    raise ValueError(f"Unrecognized Date format: {date_str}")


def _parse_solution_value(raw: Any) -> Any:
    if isinstance(raw, Date):
        return raw
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        # Date
        if s.startswith("Date("):
            return _parse_date_string(s)
        # Bool-ish
        ls = s.lower()
        if ls in ("true", "1", "yes", "y", "t"):
            return True
        if ls in ("false", "0", "no", "n", "f"):
            return False
        # Int
        try:
            return int(s)
        except Exception:
            pass
    return raw


def validate_constraint_solution(
    constraint_code: str, solution: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Execute constraint_code with a validation-only builder and evaluate
    the provided concrete solution.
    """
    builder = EvalBuilder()
    ctx = builder.get_execution_context()

    try:
        exec(constraint_code, ctx)
    except Exception as e:
        return False, f"Error executing constraint code: {e}"

    solver = ctx.get("result") or ctx.get("builder") or builder

    # Set values
    for var_name, raw_val in solution.items():
        parsed = _parse_solution_value(raw_val)
        if var_name in solver.date_vars:
            if not isinstance(parsed, Date):
                return False, f"Variable {var_name} expects Date, got {parsed}"
            solver.date_vars[var_name].set_value(parsed.year, parsed.month, parsed.day)
        elif var_name in solver.int_vars:
            if not isinstance(parsed, int):
                return False, f"Variable {var_name} expects int, got {parsed}"
            solver.int_vars[var_name].set_value(parsed)
        elif var_name in solver.bool_vars:
            if not isinstance(parsed, bool):
                return False, f"Variable {var_name} expects bool, got {parsed}"
            solver.bool_vars[var_name].set_value(parsed)
        else:
            # Ignore unknown variables; they might be unused
            continue

    # Evaluate constraints
    try:
        for c in solver.constraints:
            if isinstance(c, bool):
                if not c:
                    return False, "Constraint evaluated False"
            elif isinstance(c, ConstraintWrapper):
                if not c.evaluate():
                    return False, "Constraint evaluated False"
            elif callable(c):
                if not c():
                    return False, "Constraint evaluated False"
            else:
                if not bool(c):
                    return False, "Constraint evaluated False"
    except Exception as e:
        return False, f"Error during constraint evaluation: {e}"

    return True, "Solution validated successfully"

