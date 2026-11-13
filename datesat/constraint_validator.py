"""
Constraint validation for solved assignments.

This module executes generated constraint code using a lightweight builder that
supports date, int, and bool variables, and then evaluates all constraints
against a provided concrete solution (no solving capability).

The date operations (validity, ordering, Date + Period) follow one of two
semantics:

  * "verus": the Verus oracle (proofs/src/oracle.rs), the executable reference
    semantics, proved equal to semantics::Date in proofs/src/semantics.rs. A model
    validated this way satisfies the constraints under the semantics the
    equisatisfiability proofs are about.
  * "python": datesat.core.Date, an independent Python implementation of the same
    calendar.

"auto" (the default) uses the Verus oracle when it is built and falls back to
Python with a warning otherwise. DATESAT_VALIDATION_SEMANTICS overrides the default.
Booleans, integers and date components are evaluated in Python either way.
"""

import os
from typing import Any, Dict, Optional, Tuple, Union
import warnings

from .core import Date, Period, PYTHON_YEAR_MAX, PYTHON_YEAR_MIN
from . import verus_oracle


# Deferred constraints and Boolean connectives for evaluating a model in Python
def _wrap_constraint(constraint: Any) -> "ConstraintWrapper":
    """Wrap a constraint in ConstraintWrapper if it's not already wrapped."""
    if isinstance(constraint, ConstraintWrapper):
        return constraint
    elif isinstance(constraint, bool):
        # Use default argument to capture value, not reference
        return ConstraintWrapper(lambda c=constraint: c)
    elif callable(constraint):
        return ConstraintWrapper(constraint)
    else:
        # Check if this is a variable object with get_value() method (EvalBoolVar, EvalIntVar, etc.)
        # These should be evaluated by calling get_value(), not by calling the object itself
        if hasattr(constraint, "get_value"):
            # Capture the object with a default argument and call get_value()
            return ConstraintWrapper(lambda obj=constraint: bool(obj.get_value()))
        # Try to convert to bool, capture value with default argument
        return ConstraintWrapper(lambda c=constraint: bool(c))


def Or_eval(*args) -> "ConstraintWrapper":
    """Wrapper for Z3's Or() that works with ConstraintWrapper objects."""
    wrapped_args = [_wrap_constraint(arg) for arg in args]
    # Create tuple and capture as default argument to prevent closure issues
    wrapped_args_tuple = tuple(wrapped_args)
    return ConstraintWrapper(
        func=lambda wrapped=wrapped_args_tuple: any(c.evaluate() for c in wrapped),
        or_constraints=list(wrapped_args_tuple),
    )


def And_eval(*args) -> "ConstraintWrapper":
    """Wrapper for Z3's And() that works with ConstraintWrapper objects."""
    wrapped_args = [_wrap_constraint(arg) for arg in args]
    # Create a tuple instead of list to ensure immutability and prevent accidental sharing
    wrapped_args_tuple = tuple(wrapped_args)
    return ConstraintWrapper(
        func=lambda wrapped=wrapped_args_tuple: all(c.evaluate() for c in wrapped)
    )


def Not_eval(arg) -> "ConstraintWrapper":
    """Wrapper for Z3's Not() that works with ConstraintWrapper objects."""
    wrapped_arg = _wrap_constraint(arg)
    # Capture as default argument to prevent closure issues
    return ConstraintWrapper(func=lambda wrapped=wrapped_arg: not wrapped.evaluate())


def Implies_eval(antecedent, consequent) -> "ConstraintWrapper":
    """Wrapper for Z3's Implies() that works with ConstraintWrapper objects."""
    wrapped_antecedent = _wrap_constraint(antecedent)
    wrapped_consequent = _wrap_constraint(consequent)
    # Explicitly capture as default arguments to avoid closure issues
    return ConstraintWrapper(
        func=lambda ant=wrapped_antecedent, cons=wrapped_consequent: not ant.evaluate()
        or cons.evaluate()
    )


class ConstraintWrapper:
    """Wrapper for deferred constraint evaluation."""

    def __init__(
        self, func, var_ref=None, concrete_value=None, rhs_ref=None, or_constraints=None
    ):
        self.func = func
        self.var_ref = var_ref
        self.concrete_value = concrete_value
        self.rhs_ref = rhs_ref  # For equality constraints: x == expr, store expr here
        self.or_constraints = (
            or_constraints  # For OR constraints: list of ConstraintWrapper objects
        )

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


# Python's datetime.date covers years 1..9999. With python_bounds, every encoding
# bounds each date it computes, including every Date + Period result, to that range
# (see _add_bounds in datesat/symbolic_int/); by default dates are unbounded.
_YEAR_MIN, _YEAR_MAX = PYTHON_YEAR_MIN, PYTHON_YEAR_MAX

# The Date + Period results built by the constraint code being validated.
# validate_constraint_solution() clears it and, with python_bounds, checks that each
# one is in range.
_DERIVED_DATES: list = []


class DateRangeError(Exception):
    """A date fell outside years 1..9999 while python_bounds is in force."""


def _in_python_range(d: Date) -> bool:
    return _YEAR_MIN <= d.year <= _YEAR_MAX


# ── Date semantics ─────────────────────────────────────────────────────────

class SemanticsDisagreement(RuntimeError):
    """The Verus oracle accepted a date that datesat.core.Date rejects."""


class _PythonSemantics:
    name = "python"

    def make_date(self, y: int, m: int, d: int) -> Optional[Date]:
        try:
            return Date(y, m, d)
        except ValueError:
            return None

    def lt(self, a: Date, b: Date) -> bool:
        return a < b

    def add_period(self, d: Date, years: int, months: int, days: int) -> Date:
        return d + Period(years, months, days)


class _VerusSemantics:
    """Every date operation is answered by the Verus oracle. Dates are still held in
    datesat.core.Date objects, which only carry (y, m, d); constructing one from a
    date the oracle accepts raises SemanticsDisagreement if Python disagrees."""

    name = "verus"

    def __init__(self, oracle: "verus_oracle.VerusOracle"):
        self.oracle = oracle

    @staticmethod
    def _hold(y: int, m: int, d: int) -> Date:
        try:
            return Date(y, m, d)
        except ValueError as e:
            raise SemanticsDisagreement(
                f"Verus oracle accepts {y}-{m}-{d} but datesat.core.Date rejects it") from e

    def make_date(self, y: int, m: int, d: int) -> Optional[Date]:
        return self._hold(y, m, d) if self.oracle.is_valid(y, m, d) else None

    def lt(self, a: Date, b: Date) -> bool:
        return self.oracle.lt(a._ymd(), b._ymd())

    def add_period(self, d: Date, years: int, months: int, days: int) -> Date:
        return self._hold(*self.oracle.add_period(d._ymd(), years, months, days))


_PYTHON = _PythonSemantics()
_SEMANTICS: Any = _PYTHON
_warned_fallback = False


def _select_semantics(semantics: Optional[str]):
    global _warned_fallback
    if semantics is None:
        semantics = os.environ.get("DATESAT_VALIDATION_SEMANTICS", "auto")
    if semantics == "python":
        return _PYTHON
    if semantics == "verus":
        if not verus_oracle.oracle_available():
            raise verus_oracle.OracleUnavailable(
                f"semantics='verus' but the Verus oracle is not built at {verus_oracle.oracle_path()}")
        return _VerusSemantics(verus_oracle.shared_oracle())
    if semantics == "auto":
        if verus_oracle.oracle_available():
            return _VerusSemantics(verus_oracle.shared_oracle())
        if not _warned_fallback:
            warnings.warn(
                f"Verus oracle not built at {verus_oracle.oracle_path()}; validating with "
                "datesat.core.Date instead (pass semantics='verus' to require the oracle)")
            _warned_fallback = True
        return _PYTHON
    raise ValueError(f"unknown semantics {semantics!r}: expected 'verus', 'python' or 'auto'")


def _make_date(y: int, m: int, d: int) -> Optional[Date]:
    """The date (y, m, d), or None if it is not a valid date."""
    return _SEMANTICS.make_date(y, m, d)


def _compare(op: str, a: Date, b: Date) -> bool:
    eq = a._ymd() == b._ymd()  # equality is component-wise in every semantics
    if op == "eq":
        return eq
    if op == "ne":
        return not eq
    if op == "lt":
        return _SEMANTICS.lt(a, b)
    if op == "le":
        return eq or _SEMANTICS.lt(a, b)
    if op == "gt":
        return _SEMANTICS.lt(b, a)
    if op == "ge":
        return eq or _SEMANTICS.lt(b, a)
    raise ValueError(op)


def _add_period(d: Date, years: int, months: int, days: int) -> Date:
    """Date + Period: add years and months, clamp the day to the end of the month,
    then add days. Defined for every year; the range check under python_bounds is
    done by validate_constraint_solution()."""
    return _SEMANTICS.add_period(d, years, months, days)


class EvalDateVar:
    def __init__(self, name: str):
        self.name = name
        self._value: Optional[Date] = None
        self._lazy_op = None  # ("add"|"sub", EvalDateVar, Period)

    def set_value(self, year: int, month: int, day: int) -> None:
        self._value = _make_date(year, month, day)

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
            # Date - Period is Date + (-Period), as in the solver.
            sign = 1 if op_type == "add" else -1
            self._value = _add_period(
                left_val, sign * period.years, sign * period.months, sign * period.days
            )
        return self._value

    # comparisons
    def _cmp(self, op: str, other: Union[Date, "EvalDateVar"]) -> ConstraintWrapper:
        def compare():
            lhs = self.get_value()
            if lhs is None:
                return False
            rhs_val: Optional[Date]
            if isinstance(other, Date):
                rhs_val = other
            else:
                rhs_val = other.get_value()
            if rhs_val is None:
                return False
            return _compare(op, lhs, rhs_val)

        concrete_value = other if isinstance(other, Date) else None
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
        _DERIVED_DATES.append(out)
        return out

    def __sub__(self, other: Period) -> "EvalDateVar":
        if not isinstance(other, Period):
            raise TypeError("Can only subtract Period from DateVar")
        out = EvalDateVar(f"{self.name}_minus")
        out._lazy_op = ("sub", self, other)
        _DERIVED_DATES.append(out)
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

    def _get_component_value(self) -> Optional[int]:
        """Return the concrete component value (year/month/day) or None."""
        d = self.parent.get_value()
        if d is None:
            return None
        # Works for both bounded and unbounded Date
        return getattr(d, self.attr)

    def _cmp(self, op: str, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:
        def compare():
            component_val = self._get_component_value()
            if component_val is None:
                return False

            # Handle EvalIntVar on the right
            if isinstance(other, EvalIntVar):
                other_val = other.get_value()
            # Handle another date component on the right (e.g., D4.month <= D3.day)
            elif isinstance(other, EvalDateComponent):
                other_val = other._get_component_value()
            else:
                try:
                    other_val = int(other)
                except Exception:
                    other_val = None

            if other_val is None:
                return False

            try:
                return getattr(component_val, f"__{op}__")(other_val)
            except (OverflowError, ZeroDivisionError, ValueError, TypeError):
                return False

        return ConstraintWrapper(compare)

    def __eq__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("eq", other)
    
    def __ne__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:  # type: ignore[override]
        return self._cmp("ne", other)
    
    def __lt__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:
        return self._cmp("lt", other)
    
    def __le__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:
        return self._cmp("le", other)
    
    def __gt__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:
        return self._cmp("gt", other)
    
    def __ge__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> ConstraintWrapper:
        return self._cmp("ge", other)

    # Arithmetic operations returning EvalIntVar so that expressions like
    # D4.year * 1982 or (D7.day + I0) are supported during validation.
    def _binary_int_op(self, op: str, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.parent.name}_{self.attr}_{op}")

        def compute():
            lhs = self._get_component_value()
            if lhs is None:
                # Debug: check if parent is set
                parent_val = self.parent.get_value()
                if parent_val is None:
                    # Parent date variable hasn't been set - this is likely the bug
                    import warnings
                    warnings.warn(f"Parent date variable {self.parent.name} not set when evaluating {self.parent.name}.{self.attr} {op} {other}")
                return None
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if rv is None:
                return None
            try:
                return getattr(lhs, f"__{op}__")(rv)
            except (OverflowError, ZeroDivisionError, ValueError):
                return None

        out.get_value = compute  # type: ignore[attr-defined]
        return out

    def __add__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self._binary_int_op("add", other)

    def __radd__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self.__add__(other)

    def __sub__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self._binary_int_op("sub", other)

    def __rsub__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        # Implement as (other - component)
        out = EvalIntVar(f"const_minus_{self.parent.name}_{self.attr}")

        def compute():
            rhs = self._get_component_value()
            if rhs is None:
                return None
            if isinstance(other, EvalIntVar):
                lv = other.get_value()
            else:
                try:
                    lv = int(other)
                except Exception:
                    lv = None
            if lv is None:
                return None
            try:
                return getattr(lv, "__sub__")(rhs)
            except (OverflowError, ZeroDivisionError, ValueError):
                return None

        out.get_value = compute  # type: ignore[attr-defined]
        return out

    def __mul__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self._binary_int_op("mul", other)

    def __rmul__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self.__mul__(other)

    # Integer division using `/` in the DSL
    def __truediv__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        # Delegate to floordiv semantics for integer division
        return self._binary_int_op("floordiv", other)

    def __rtruediv__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        # Implement as (other / component) with floor semantics
        out = EvalIntVar(f"const_div_{self.parent.name}_{self.attr}")

        def compute():
            rhs = self._get_component_value()
            if rhs is None or rhs == 0:
                return None
            if isinstance(other, EvalIntVar):
                lv = other.get_value()
            else:
                try:
                    lv = int(other)
                except Exception:
                    lv = None
            if lv is None:
                return None
            try:
                return lv // rhs
            except (OverflowError, ZeroDivisionError, ValueError):
                return None

        out.get_value = compute  # type: ignore[attr-defined]
        return out

    def __mod__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        return self._binary_int_op("mod", other)

    def __rmod__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        # Implement as (other % component)
        out = EvalIntVar(f"const_mod_{self.parent.name}_{self.attr}")

        def compute():
            rhs = self._get_component_value()
            if rhs is None or rhs == 0:
                return None
            if isinstance(other, EvalIntVar):
                lv = other.get_value()
            else:
                try:
                    lv = int(other)
                except Exception:
                    lv = None
            if lv is None:
                return None
            try:
                return getattr(lv, "__mod__")(rhs)
            except (OverflowError, ZeroDivisionError, ValueError):
                return None

        out.get_value = compute  # type: ignore[attr-defined]
        return out


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
            # Support comparisons against another EvalIntVar
            if isinstance(other, EvalIntVar):
                return other.get_value()

            # Support comparisons where the *right-hand side* is a date component
            # such as D6.month or D3.day. The parser may generate expressions like
            # "I6 > D6.month", which should be valid and interpreted as an int
            # comparison, just like "D6.month < I6".
            from .constraint_validator import EvalDateComponent  # type: ignore

            if isinstance(other, EvalDateComponent):
                return other._get_component_value()

            # Fallback: treat as a plain integer literal
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

    def __add__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_plus")

        def compute():
            lhs = self.get_value()
            # Support addition with another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support addition with a date component (e.g., I8 + D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None:
                return None
            return lhs + rv

        out.get_value = compute  # type: ignore
        return out

    def __sub__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_minus")

        def compute():
            lhs = self.get_value()
            # Support subtraction with another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support subtraction with a date component (e.g., I8 - D5.year or x.year * 2 - x.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None:
                return None
            return lhs - rv

        out.get_value = compute  # type: ignore
        return out

    def __mul__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_times")

        def compute():
            lhs = self.get_value()
            # Support multiplication with another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support multiplication with a date component (e.g., I8 * D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None:
                return None
            return lhs * rv

        out.get_value = compute  # type: ignore
        return out

    def __floordiv__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_div")

        def compute():
            lhs = self.get_value()
            # Support division by another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support division by a date component (e.g., I8 // D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None or rv == 0:
                return None
            return lhs // rv

        out.get_value = compute  # type: ignore
        return out

    def __mod__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_mod")

        def compute():
            lhs = self.get_value()
            # Support modulo with another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support modulo with a date component (e.g., I8 % D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None or rv == 0:
                return None
            return lhs % rv

        out.get_value = compute  # type: ignore
        return out

    def __pow__(self, other: Union[int, "EvalIntVar", "EvalDateComponent"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_pow")

        def compute():
            lhs = self.get_value()
            # Support exponentiation with another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support exponentiation with a date component (e.g., I8 ** D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None:
                return None
            try:
                return lhs ** rv
            except (OverflowError, ValueError):
                return None

        out.get_value = compute  # type: ignore
        return out

    # Reverse operations for when int is on the left side
    def __radd__(self, other: int) -> "EvalIntVar":
        return self.__add__(other)

    def __rsub__(self, other: int) -> "EvalIntVar":
        out = EvalIntVar(f"const_minus_{self.name}")

        def compute():
            rhs = self.get_value()
            if rhs is None:
                return None
            return int(other) - rhs

        out.get_value = compute  # type: ignore
        return out

    def __rmul__(self, other: int) -> "EvalIntVar":
        return self.__mul__(other)

    # Integer division using `/` in the DSL
    def __truediv__(self, other: Union[int, "EvalIntVar"]) -> "EvalIntVar":
        out = EvalIntVar(f"{self.name}_div")

        def compute():
            lhs = self.get_value()
            # Support division by another EvalIntVar
            if isinstance(other, EvalIntVar):
                rv = other.get_value()
            # Support division by a date component (e.g., I8 / D5.year)
            elif isinstance(other, EvalDateComponent):
                rv = other._get_component_value()
            else:
                try:
                    rv = int(other)
                except Exception:
                    rv = None
            if lhs is None or rv is None or rv == 0:
                return None
            return lhs // rv

        out.get_value = compute  # type: ignore
        return out

    def __rtruediv__(self, other: int) -> "EvalIntVar":
        out = EvalIntVar(f"const_div_{self.name}")

        def compute():
            rhs = self.get_value()
            if rhs is None or rhs == 0:
                return None
            return int(other) // rhs

        out.get_value = compute  # type: ignore
        return out

    def __rmod__(self, other: int) -> "EvalIntVar":
        out = EvalIntVar(f"const_mod_{self.name}")

        def compute():
            rhs = self.get_value()
            if rhs is None or rhs == 0:
                return None
            return int(other) % rhs

        out.get_value = compute  # type: ignore
        return out

    def __rpow__(self, other: int) -> "EvalIntVar":
        out = EvalIntVar(f"const_pow_{self.name}")

        def compute():
            rhs = self.get_value()
            if rhs is None:
                return None
            try:
                return int(other) ** rhs
            except (OverflowError, ValueError):
                return None

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
        return And_eval(self, other)

    def __or__(self, other: Any) -> ConstraintWrapper:
        return Or_eval(self, other)


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
        return Or_eval(*args)

    def And(self, *args) -> ConstraintWrapper:
        return And_eval(*args)

    def Not(self, arg) -> ConstraintWrapper:
        return Not_eval(arg)

    def Implies(self, antecedent, consequent) -> ConstraintWrapper:
        return Implies_eval(antecedent, consequent)

    # constraint collector
    def add_constraint(self, constraint: Any) -> None:
        self.constraints.append(constraint)

    # context for exec
    def get_execution_context(self) -> Dict[str, Any]:
        import builtins

        class MockZ3:
            Or = staticmethod(lambda *args: Or_eval(*args))
            And = staticmethod(lambda *args: And_eval(*args))
            Not = staticmethod(lambda arg: Not_eval(arg))
            Implies = staticmethod(lambda a, c: Implies_eval(a, c))
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
                    return _make_date(int(y), int(m), int(d))
                
                lazy_date.get_value = get_date_value  # type: ignore
                return lazy_date
            else:
                # A concrete literal. It is wrapped in an EvalDateVar so that comparing
                # it, or adding a Period to it, also goes through the semantics.
                value = _make_date(int(year), int(month), int(day))
                if value is None:
                    raise ValueError(f"Invalid date: Date({year}, {month}, {day})")
                literal = EvalDateVar(f"Date({year}, {month}, {day})")
                literal.get_value = lambda: value  # type: ignore
                return literal

        return {
            "Date": DateWrapper,
            "Period": Period,
            "DateSATBuilder": lambda: self,
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
        value = _make_date(y, m, d)
        if value is None:
            raise ValueError(f"Invalid date: {date_str}")
        return value
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
    constraint_code: str,
    solution: Dict[str, Any],
    python_bounds: bool = False,
    semantics: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Execute constraint_code with a validation-only builder and evaluate
    the provided concrete solution.

    With python_bounds (matching datesat.solve(..., python_bounds=True)), every date
    value and every Date + Period result must lie in years 1..9999, wherever the
    expression appears; otherwise the model is rejected. By default any
    calendar-valid proleptic Gregorian date is accepted.

    semantics selects how date operations are evaluated: "verus" (the Verus oracle,
    required), "python" (datesat.core.Date) or "auto" (the oracle if built,
    otherwise Python). None means $DATESAT_VALIDATION_SEMANTICS, or "auto".
    """
    global _SEMANTICS
    _SEMANTICS = _select_semantics(semantics)
    try:
        return _validate(constraint_code, solution, python_bounds)
    finally:
        _SEMANTICS = _PYTHON


def validation_semantics(semantics: Optional[str] = None) -> str:
    """The semantics validate_constraint_solution(semantics=...) would use: "verus" or
    "python"."""
    return _select_semantics(semantics).name


def _validate(
    constraint_code: str, solution: Dict[str, Any], python_bounds: bool
) -> Tuple[bool, str]:
    _DERIVED_DATES.clear()
    builder = EvalBuilder()
    ctx = builder.get_execution_context()

    try:
        exec(constraint_code, ctx)
    except Exception as e:
        return False, f"Error executing constraint code: {e}"

    solver = ctx.get("result") or ctx.get("builder") or builder

    # Set values
    for var_name, raw_val in solution.items():
        try:
            parsed = _parse_solution_value(raw_val)
        except (ValueError, SemanticsDisagreement) as e:
            return False, f"Variable {var_name}: {e}"
        if var_name in solver.date_vars:
            if not isinstance(parsed, Date):
                return False, f"Variable {var_name} expects Date, got {parsed}"
            if python_bounds and not _in_python_range(parsed):
                return False, f"Variable {var_name} = {parsed} is outside years 1..9999"
            solver.date_vars[var_name].set_value(parsed.year, parsed.month, parsed.day)
            if solver.date_vars[var_name].get_value() is None:
                return False, f"Variable {var_name} = {parsed} is not a valid date"
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

    # With python_bounds the solver asserts every Date + Period result is in years
    # 1..9999 wherever the expression appears, so a model that breaks this is invalid
    # even when that result is negated or sits in a disjunct that is never evaluated.
    if python_bounds:
        for derived in _DERIVED_DATES:
            try:
                value = derived.get_value()
            except ArithmeticError as e:
                return False, f"Error computing {derived.name}: {e}"
            if value is not None and not _in_python_range(value):
                return False, f"Date + Period result out of range: {derived.name} = {value}"

    # Evaluate constraints
    try:
        for c in solver.constraints:
            if isinstance(c, bool):
                holds = c
            elif isinstance(c, ConstraintWrapper):
                holds = c.evaluate()
            elif callable(c):
                holds = c()
            else:
                holds = bool(c)
            if not holds:
                return False, "Constraint evaluated False"
    except Exception as e:
        return False, f"Error during constraint evaluation: {e}"

    return True, "Solution validated successfully"

