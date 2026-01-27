"""
Constraint parser for Date-SMT system using Lark parser generator.

This module provides functionality to parse constraints from the structured format
and convert them into executable DateSMTBuilder code using a context-free grammar.
"""

import re
from typing import Any, Dict, List, Union

from lark import Lark, Transformer


class ConstraintTransformer(Transformer):
    """Transformer to convert Lark parse tree to Python code."""

    def __init__(self, variable_types: Dict[str, str] = None):
        """
        Initialize transformer with variable type information.

        Args:
            variable_types: Dictionary mapping variable names to types ('date', 'int', 'bool')
        """
        super().__init__()
        self.variable_types = variable_types or {}

    def constraint(self, items) -> str:
        """Transform constraint (top level)."""
        bool_expr = items[0]

        # Check if bool_expr already has builder.add_constraint wrapper (from implication)
        if bool_expr.startswith("builder.add_constraint("):
            return bool_expr

        return f"builder.add_constraint({bool_expr})"

    def implication(self, items) -> str:
        """Transform implication A -> B into Implies(A, B)."""
        # Earley parser might include the -> token, filter it out
        filtered = [item for item in items if str(item) != "->"]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
        else:
            # Fallback: use first and last items
            left = str(items[0])
            right = str(items[-1])

        # Strip outermost parentheses from arguments if present
        # e.g., (a == b) -> (c == d) becomes Implies(a == b, c == d)
        left = self._strip_outer_parens(left)
        right = self._strip_outer_parens(right)

        return f"Implies({left}, {right})"

    def _strip_outer_parens(self, expr: str) -> str:
        """Strip outermost parentheses from an expression if they wrap the entire expression."""
        expr = expr.strip()
        if expr.startswith("(") and expr.endswith(")"):
            # Check if these are the outermost matching parentheses
            depth = 0
            for i, char in enumerate(expr):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    # If depth hits 0 before the end, these aren't the outermost parens
                    if depth == 0 and i < len(expr) - 1:
                        return expr
            # If we get here, the parentheses wrap the whole expression
            return expr[1:-1]
        return expr

    def or_op(self, items) -> str:
        """Transform OR operation A || B into Or(A, B)."""
        # Earley parser might include the operator token, filter it out
        filtered = [item for item in items if str(item) not in ("||", "or", "OR")]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
        else:
            # Fallback: use first and last items
            left = str(items[0])
            right = str(items[-1])

        # Strip outermost parentheses from arguments
        left = self._strip_outer_parens(left)
        right = self._strip_outer_parens(right)

        return f"Or({left}, {right})"

    def and_op(self, items) -> str:
        """Transform AND operation A && B into And(A, B)."""
        # Earley parser might include the operator token, filter it out
        filtered = [item for item in items if str(item) not in ("&&", "and", "AND")]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
        else:
            # Fallback: use first and last items
            left = str(items[0])
            right = str(items[-1])

        # Strip outermost parentheses from arguments
        left = self._strip_outer_parens(left)
        right = self._strip_outer_parens(right)

        return f"And({left}, {right})"

    def not_op(self, items) -> str:
        """Transform NOT operation !A / not A into Not(A)."""
        # items = [NOT token, not_expr] or [not_expr] if NOT token is stripped
        filtered = [item for item in items if str(item) not in ("!", "not", "NOT")]
        if filtered:
            expr = str(filtered[0])
        else:
            expr = str(items[-1])

        # Strip outermost parentheses from argument
        expr = self._strip_outer_parens(expr)

        return f"Not({expr})"

    def eq_bool(self, items) -> str:
        """Transform boolean equality A == B."""
        filtered = [item for item in items if str(item) != "=="]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
            return f"{left} == {right}"
        return f"{items[0]} == {items[-1]}"

    def ne_bool(self, items) -> str:
        """Transform boolean inequality A != B."""
        filtered = [item for item in items if str(item) != "!="]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
            return f"{left} != {right}"
        return f"{items[0]} != {items[-1]}"

    def bool_atom(self, items) -> str:
        """Transform boolean atom (comparison, variable, bool literal, or parenthesized bool expr)."""
        # Handle parenthesized expressions: LPAR bool_expr RPAR
        # Always preserve parentheses from input
        if len(items) == 3 and str(items[0]) == "(" and str(items[2]) == ")":
            return f"({items[1]})"
        if len(items) == 1:
            return str(items[0])
        return " ".join(str(item) for item in items)

    def date_comparison(self, items) -> str:
        """Transform date comparison expression."""
        return self._comparison_helper(items)

    def int_comparison(self, items) -> str:
        """Transform int comparison expression."""
        return self._comparison_helper(items)

    def _comparison_helper(self, items) -> str:
        """Helper for transforming comparison expressions (both date and int)."""
        left, op, right = items

        # Convert to strings (items could be Tree objects if not fully transformed)
        left_str = str(left)
        op_str = str(op)
        right_str = str(right)

        # Check if we need to transform parametric Date() comparisons
        # (Date constructors with variable arguments, e.g., Date(x, 2, 1))
        transformed = self._transform_parametric_date_comparison(
            left_str, op_str, right_str
        )
        if transformed:
            return transformed
        return f"{left_str} {op_str} {right_str}"

    def bool_literal(self, items) -> str:
        """Transform boolean literal True/False."""
        return str(items[0])

    def _extract_date_components(self, expr: str) -> List[str]:
        """
        Extract year, month, day arguments from a Date(...) constructor expression.

        Args:
            expr: An expression that may contain Date(year, month, day)

        Returns:
            List of [year, month, day] argument strings, or None if not a valid Date()
        """
        # Find Date( and match balanced parentheses
        date_start = expr.find("Date(")
        if date_start == -1:
            return None

        # Find the opening paren after Date
        start = date_start + 5  # len("Date(")
        paren_count = 0
        args = []
        current_arg = []
        i = start

        while i < len(expr):
            char = expr[i]
            if char == "(":
                paren_count += 1
                current_arg.append(char)
            elif char == ")":
                if paren_count == 0:
                    # This is the closing paren for Date()
                    if current_arg:
                        args.append("".join(current_arg).strip())
                    break
                paren_count -= 1
                current_arg.append(char)
            elif char == "," and paren_count == 0:
                # This comma separates arguments
                args.append("".join(current_arg).strip())
                current_arg = []
            else:
                current_arg.append(char)
            i += 1

        if len(args) == 3:
            return args
        return None

    @staticmethod
    def _has_variable(expr: str) -> bool:
        """
        Check if expression contains a variable (not just a literal number).

        Used to determine if a Date() constructor is parametric.
        """
        expr = expr.strip()
        # If it's just a number, it has no variable
        if re.match(r"^-?\d+$", expr):
            return False
        # If it contains identifier characters, it has a variable
        return bool(re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", expr))

    def _transform_parametric_date_comparison(
        self, left: str, op: str, right: str
    ) -> str:
        """
        Transform comparisons involving parametric Date() constructors.

        A parametric Date() has one or more variable arguments, e.g., Date(x, 2, 1).
        This is different from a date variable (e.g., `k` where `k: date`).

        Transforms:
            k >= Date(x+1, 1, 1)  →  component-wise comparison on k.year, k.month, k.day
            k == Date(x, 1, 2)   →  And(k.year == x, k.month == 1, k.day == 2)

        Args:
            left: Left side of comparison (e.g., "k" or "Date(x, 2, 1)")
            op: Comparison operator (==, !=, >=, <=, >, <)
            right: Right side of comparison

        Returns:
            Transformed constraint string, or None if no transformation needed
        """
        import re

        # Check if right side is a Date() constructor
        date_components = self._extract_date_components(right)
        date_var_expr = left.strip()
        swapped = False

        if not date_components:
            # Check if left side is a Date() constructor
            date_components = self._extract_date_components(left)
            if date_components:
                # Swap left and right, invert operator
                date_var_expr = right.strip()
                op = self._invert_operator(op)
                swapped = True
            else:
                return None

        year_expr, month_expr, day_expr = date_components

        # If all components are concrete (no variables), no transformation needed
        if not (
            self._has_variable(year_expr)
            or self._has_variable(month_expr)
            or self._has_variable(day_expr)
        ):
            return None

        # Extract the date variable name (handle property access like x.year)
        date_var_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", date_var_expr)
        if not date_var_match:
            return None

        date_var = date_var_match.group(1)

        # Transform based on operator
        if op == "==":
            # Equality: all components must match
            return f"And({date_var}.year == {year_expr}, {date_var}.month == {month_expr}, {date_var}.day == {day_expr})"
        elif op == "!=":
            # Inequality: at least one component differs
            return f"Or({date_var}.year != {year_expr}, {date_var}.month != {month_expr}, {date_var}.day != {day_expr})"
        elif op == ">=":
            # Greater or equal: lexicographic comparison
            return f"Or({date_var}.year > {year_expr}, And({date_var}.year == {year_expr}, Or({date_var}.month > {month_expr}, And({date_var}.month == {month_expr}, {date_var}.day >= {day_expr}))))"
        elif op == "<=":
            # Less or equal: lexicographic comparison
            return f"Or({date_var}.year < {year_expr}, And({date_var}.year == {year_expr}, Or({date_var}.month < {month_expr}, And({date_var}.month == {month_expr}, {date_var}.day <= {day_expr}))))"
        elif op == ">":
            # Greater: lexicographic comparison (year > OR (year == AND month >) OR (year == AND month == AND day >))
            return f"Or({date_var}.year > {year_expr}, And({date_var}.year == {year_expr}, Or({date_var}.month > {month_expr}, And({date_var}.month == {month_expr}, {date_var}.day > {day_expr}))))"
        elif op == "<":
            # Less: lexicographic comparison (year < OR (year == AND month <) OR (year == AND month == AND day <))
            return f"Or({date_var}.year < {year_expr}, And({date_var}.year == {year_expr}, Or({date_var}.month < {month_expr}, And({date_var}.month == {month_expr}, {date_var}.day < {day_expr}))))"

        return None

    def _invert_operator(self, op: str) -> str:
        """Invert a comparison operator."""
        inversions = {
            ">=": "<=",
            "<=": ">=",
            ">": "<",
            "<": ">",
            "==": "==",
            "!=": "!=",
        }
        return inversions.get(op, op)

    # Date expression transformers
    def date_add_period(self, items) -> str:
        """Transform date + period operation."""
        filtered = [item for item in items if str(item) != "+"]
        if len(filtered) == 2:
            return f"{filtered[0]} + {filtered[1]}"
        return f"{items[0]} + {items[-1]}"

    def date_sub_period(self, items) -> str:
        """Transform date - period operation."""
        filtered = [item for item in items if str(item) != "-"]
        if len(filtered) == 2:
            return f"{filtered[0]} - {filtered[1]}"
        return f"{items[0]} - {items[-1]}"

    def date_atom(self, items) -> str:
        """Transform date atom (handle parenthesized expressions)."""
        # If it's just one item, return it
        if len(items) == 1:
            return str(items[0])
        # If it's LPAR expr RPAR, preserve parentheses for nested expressions
        if len(items) == 3 and str(items[0]) == "(" and str(items[2]) == ")":
            return f"({items[1]})"
        # Otherwise return all items joined
        return " ".join(str(item) for item in items)

    # Period expression transformers
    def period_add(self, items) -> str:
        """Transform period + period operation."""
        filtered = [item for item in items if str(item) != "+"]
        if len(filtered) == 2:
            return f"{filtered[0]} + {filtered[1]}"
        return f"{items[0]} + {items[-1]}"

    def period_sub(self, items) -> str:
        """Transform period - period operation."""
        filtered = [item for item in items if str(item) != "-"]
        if len(filtered) == 2:
            return f"{filtered[0]} - {filtered[1]}"
        return f"{items[0]} - {items[-1]}"

    def int_mul_period(self, items) -> str:
        """Transform int * period operation."""
        filtered = [item for item in items if str(item) != "*"]
        if len(filtered) == 2:
            return f"{filtered[0]} * {filtered[1]}"
        return f"{items[0]} * {items[-1]}"

    def period_mul_int(self, items) -> str:
        """Transform period * int operation."""
        filtered = [item for item in items if str(item) != "*"]
        if len(filtered) == 2:
            return f"{filtered[0]} * {filtered[1]}"
        return f"{items[0]} * {items[-1]}"

    def period_atom(self, items) -> str:
        """Transform period atom (handle parenthesized expressions)."""
        if len(items) == 1:
            return str(items[0])
        if len(items) == 3 and str(items[0]) == "(" and str(items[2]) == ")":
            return f"({items[1]})"
        return " ".join(str(item) for item in items)

    # Integer expression transformers
    def int_add(self, items) -> str:
        """Transform integer addition operation."""
        filtered = [item for item in items if str(item) != "+"]
        if len(filtered) == 2:
            return f"{filtered[0]} + {filtered[1]}"
        return f"{items[0]} + {items[-1]}"

    def int_sub(self, items) -> str:
        """Transform integer subtraction operation."""
        filtered = [item for item in items if str(item) != "-"]
        if len(filtered) == 2:
            return f"{filtered[0]} - {filtered[1]}"
        return f"{items[0]} - {items[-1]}"

    def int_mul(self, items) -> str:
        """Transform integer multiplication (linear only: const * var or var * const)."""
        filtered = [item for item in items if str(item) != "*"]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
        else:
            left = str(items[0])
            right = str(items[-1])

        # Validate linearity: one side must be a constant
        left_is_const = self._is_constant(left)
        right_is_const = self._is_constant(right)

        if not (left_is_const or right_is_const):
            raise ValueError(
                f"Nonlinear arithmetic not allowed: '{left} * {right}'. "
                f"Multiplication must be between a constant and a variable (e.g., '5 * x' or 'x * 5')."
            )

        return f"{left} * {right}"

    def int_neg(self, items) -> str:
        """Transform integer negation operation."""
        filtered = [item for item in items if str(item) != "-"]
        if filtered:
            return f"-{filtered[0]}"
        return f"-{items[-1]}"

    def int_atom(self, items) -> str:
        """Transform int atom (handle parenthesized expressions). Always preserve parentheses."""
        if len(items) == 1:
            return str(items[0])
        if len(items) == 3 and str(items[0]) == "(" and str(items[2]) == ")":
            return f"({items[1]})"
        return " ".join(str(item) for item in items)

    @staticmethod
    def _is_constant(expr: str) -> bool:
        """
        Check if an expression is a constant (signed number).

        Args:
            expr: Expression string to check

        Returns:
            True if the expression is a constant number, False otherwise
        """
        expr = expr.strip()
        # Remove parentheses if present
        if expr.startswith("(") and expr.endswith(")"):
            expr = expr[1:-1].strip()
        # Check if it's a signed number
        return bool(re.match(r"^-?\d+$", expr))

    # Variable transformer (unified, type checking happens at usage)
    def variable(self, items) -> str:
        """Transform variable reference."""
        return str(items[0])

    def _check_variable_type(
        self, var_name: str, expected_type: str, context: str
    ) -> None:
        """
        Check if a variable is used in the correct type context.

        Args:
            var_name: Name of the variable
            expected_type: Expected type ('date', 'int', or 'bool')
            context: Context where the variable is used (for error messages)

        Raises:
            ValueError: If variable type doesn't match expected type
        """
        if var_name not in self.variable_types:
            # Variable not in type map - will be caught later by undeclared variable check
            return

        actual_type = self.variable_types[var_name]
        if actual_type != expected_type:
            raise ValueError(
                f"Type error: Variable '{var_name}' has type '{actual_type}' but is used as '{expected_type}' "
                f"in context '{context}'. Variables must be used consistently with their declared type."
            )

    # Date field access (property access on dates)
    def date_field_access(self, items) -> str:
        """Transform date field access like x.year, x.month, x.day, or Date(...).year."""
        # items = [date_variable/date_constructor, DOT, date_field]
        date_expr = items[0]
        field_name = items[2]
        return f"{date_expr}.{field_name}"

    def date_field(self, items) -> str:
        """Transform date field name (year, month, day)."""
        return str(items[0])

    # Constructors
    def date_constructor(self, items) -> str:
        """Transform Date constructor (arguments are int_expr)."""
        # items = [LPAR, year_int_expr, month_int_expr, day_int_expr, RPAR]
        # Filter out parentheses and commas if present
        args = [str(item) for item in items if str(item) not in ["(", ")", ","]]
        if len(args) >= 3:
            return f"Date({args[0]}, {args[1]}, {args[2]})"
        # Fallback: assume items are [year, month, day]
        return f"Date({items[0]}, {items[1]}, {items[2]})"

    def period_constructor(self, items) -> str:
        """Transform Period constructor (arguments are int_expr)."""
        # items = [LPAR, years_int_expr, months_int_expr, days_int_expr, RPAR]
        # Filter out parentheses and commas if present
        args = [str(item) for item in items if str(item) not in ["(", ")", ","]]
        if len(args) >= 3:
            return f"Period({args[0]}, {args[1]}, {args[2]})"
        # Fallback: assume items are [years, months, days]
        return f"Period({items[0]}, {items[1]}, {items[2]})"

    def comparison_op(self, items) -> str:
        """Transform comparison operator."""
        if not items:
            return ""
        return str(items[0])

    def int_const(self, items) -> str:
        """Transform integer constant."""
        return str(items[0])

    # Legacy methods for backward compatibility
    def number(self, items) -> str:
        """Transform number literal (legacy)."""
        return str(items[0])

    def string(self, items) -> str:
        """Transform string literal (legacy)."""
        return str(items[0])


class ConstraintParser:
    """Parser for structured constraint format using Lark grammar."""

    def __init__(self):
        """Initialize the parser with Lark grammar."""
        self.variable_types: Dict[str, str] = (
            {}
        )  # Maps variable name to type: 'date', 'int', or 'bool'

        # Define the type-safe grammar for constraint parsing
        # Type safety is enforced by construction: int_expr, date_expr, period_expr, bool_expr
        self.grammar = r"""
            constraint: bool_expr

            // Boolean expression hierarchy with proper precedence
            ?bool_expr: implication
            
            ?implication: equality
                        | equality IMPLIES implication -> implication
            
            ?equality: disjunction
                     | disjunction EQ disjunction -> eq_bool
                     | disjunction NE disjunction -> ne_bool
            
            ?disjunction: conjunction
                        | disjunction OR conjunction -> or_op
            
            ?conjunction: negation
                        | conjunction AND negation -> and_op
            
            ?negation: NOT negation -> not_op
                     | bool_atom
            
            ?bool_atom: date_comparison
                      | int_comparison
                      | bool_literal
                      | variable
                      | LPAR bool_expr RPAR

            // Type-safe comparisons: dates compare with dates, ints compare with ints
            // Note: Variables can be either type, so both rules can match - Earley parser handles ambiguity
            // The transformer will resolve based on inferred variable types
            date_comparison: date_expr comparison_op date_expr
            int_comparison: int_expr comparison_op int_expr

            comparison_op: LT | LTE | GT | GTE | EQ | NE
            LT: "<"
            LTE: "<="
            GT: ">"
            GTE: ">="
            EQ: "=="
            NE: "!="

            // Date expressions: dates can be combined with periods
            ?date_expr: date_expr PLUS period_expr -> date_add_period
                      | date_expr MINUS period_expr -> date_sub_period
                      | date_atom
            
            ?date_atom: date_constructor
                      | variable
                      | LPAR date_expr RPAR

            date_constructor: "Date" LPAR int_expr "," int_expr "," int_expr RPAR

            // Period expressions: periods can be combined with periods or scaled by concrete integers only
            ?period_expr: period_expr PLUS period_expr -> period_add
                        | period_expr MINUS period_expr -> period_sub
                        | int_const STAR period_expr -> int_mul_period
                        | period_expr STAR int_const -> period_mul_int
                        | period_atom
            
            ?period_atom: period_constructor
                        | LPAR period_expr RPAR

            period_constructor: "Period" LPAR int_const "," int_const "," int_const RPAR

            // Integer expressions: linear arithmetic
            ?int_expr: int_expr PLUS int_term -> int_add
                     | int_expr MINUS int_term -> int_sub
                     | int_term
            
            ?int_term: int_const STAR int_term -> int_mul
                     | int_term STAR int_const -> int_mul
                     | int_factor
            
            ?int_factor: MINUS int_factor -> int_neg
                       | int_atom
            
            ?int_atom: int_const
                     | variable
                     | date_field_access
                     | LPAR int_expr RPAR

            int_const: SIGNED_NUMBER

            // Property access on dates (extracts year, month, or day as integer)
            // Allows field access on any date expression, e.g., (d + Period(1, 0, 0)).year
            date_field_access: date_expr DOT date_field
            
            date_field: DATE_FIELD
            DATE_FIELD: "year" | "month" | "day"

            // Unified variable rule (type checking happens in transformer)
            variable: CNAME
            
            // Boolean literals
            bool_literal: BOOL_LITERAL
            BOOL_LITERAL: "True" | "False"

            // Operators
            IMPLIES: "->"
            OR: "||" | /\bor\b/i | /\bOR\b/
            AND: "&&" | /\band\b/i | /\bAND\b/
            NOT: "!" | /\bnot\b/i | /\bNOT\b/
            PLUS: "+"
            MINUS: "-"
            STAR: "*"
            LPAR: "("
            RPAR: ")"
            DOT: "."

            %import common.CNAME
            %import common.SIGNED_NUMBER
            %import common.WS
            %ignore WS
        """

        # Create the Lark parser with Earley algorithm (handles ambiguities better)
        self.parser = Lark(
            self.grammar,
            parser="earley",
            start="constraint",
        )
        # Note: transformer will be recreated in generate_builder_code() with variable_types
        self.transformer = None

    def _validate_parentheses_balance(self, constraint_str: str) -> None:
        """
        Validate that parentheses are balanced in the constraint.

        Raises:
            ValueError: If parentheses are unbalanced with helpful error message
        """
        if not constraint_str:
            return

        depth = 0
        position = 0

        for i, char in enumerate(constraint_str):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    # More closing than opening parens at this position
                    context_start = max(0, i - 20)
                    context_end = min(len(constraint_str), i + 20)
                    context = constraint_str[context_start:context_end]
                    pointer = " " * (i - context_start) + "^"
                    raise ValueError(
                        f"Unbalanced parentheses: found closing ')' without matching opening '(' at position {i}\n"
                        f"  {context}\n"
                        f"  {pointer}"
                    )
            position = i

        if depth > 0:
            # More opening than closing parens
            # Find the first unmatched opening paren
            temp_depth = 0
            first_unmatched = -1
            for i, char in enumerate(constraint_str):
                if char == "(":
                    if temp_depth == 0:
                        first_unmatched = i
                    temp_depth += 1
                elif char == ")":
                    temp_depth -= 1
                    if temp_depth == 0:
                        first_unmatched = -1

            context_start = max(0, first_unmatched - 20)
            context_end = min(len(constraint_str), first_unmatched + 40)
            context = constraint_str[context_start:context_end]
            pointer = " " * (first_unmatched - context_start) + "^"
            raise ValueError(
                f"Unbalanced parentheses: {depth} unclosed opening '(' found, starting at position {first_unmatched}\n"
                f"  {context}\n"
                f"  {pointer}"
            )

    def parse_constraint(
        self, constraint_str: str, variable_types: Dict[str, str] = None
    ) -> str:
        """
        Parse a single constraint string and return the corresponding Python code.

        Args:
            constraint_str: Constraint string like "x>=Date(2000,2,28)"
            variable_types: Optional dictionary mapping variable names to types

        Returns:
            Python code string for the constraint
        """
        # Remove whitespace
        constraint_str = constraint_str.strip()

        # Check for unbalanced parentheses
        self._validate_parentheses_balance(constraint_str)

        # Check for invalid variable names that should raise ValueError
        if self._is_invalid_variable_name(constraint_str):
            raise ValueError(
                f"Could not parse constraint '{constraint_str}': Invalid variable name"
            )
        try:
            # Create transformer with variable types
            transformer = ConstraintTransformer(variable_types or self.variable_types)

            # Parse using Lark
            tree = self.parser.parse(constraint_str)

            # Validate that the parse tree is consistent with declared types
            # This catches cases where grammar is ambiguous but declared types make it clear
            if variable_types or self.variable_types:
                self._validate_parse_tree_types(
                    tree, variable_types or self.variable_types
                )

            # Apply transformer
            result = transformer.transform(tree)
            return result
        except Exception as e:
            raise ValueError(f"Could not parse constraint '{constraint_str}': {e}")

    def _is_invalid_variable_name(self, constraint_str: str) -> bool:
        """Check if the constraint contains invalid variable names."""
        # Handle empty or whitespace-only strings
        if not constraint_str or constraint_str.isspace():
            return False

        # Property names that are valid after a dot
        valid_property_names = {"year", "month", "day"}

        # Check for invalid variable names like var-123, var.123, 123var
        # But exclude cases where hyphen/dot is followed by keywords like Period/Date or '('
        # This distinguishes "var-123" (invalid) from "z-Period(...)" (valid subtraction)
        pattern1 = r"\b[a-zA-Z_][a-zA-Z0-9_]*[-.][a-zA-Z0-9_]+\b"
        matches = re.finditer(pattern1, constraint_str)
        for match in matches:
            matched_text = match.group()
            # Check if the part after hyphen/dot is a keyword (Period, Date) or a property name
            parts = re.split(r"[-.]", matched_text, maxsplit=1)
            if len(parts) == 2:
                second_part = parts[1]
                # If it's a keyword or property name, this is valid
                if (
                    second_part in ["Period", "Date"]
                    or second_part in valid_property_names
                ):
                    continue
                # Check if followed by '(' which would indicate a function call
                end_pos = match.end()
                if end_pos < len(constraint_str) and constraint_str[end_pos] == "(":
                    continue
                # Otherwise, it's an invalid variable name
                return True

        # Check for invalid variable names starting with digits like 123var
        if re.search(r"\b[0-9]+[a-zA-Z_][a-zA-Z0-9_]*\b", constraint_str):
            return True
        return False

    def extract_variable_declarations(self, constraints: List[str]) -> Dict[str, str]:
        """
        Extract variable declarations from constraints.
        Looks for patterns like "x: date", "y: int", "z: bool".

        Args:
            constraints: List of constraint strings

        Returns:
            Dictionary mapping variable names to their types ('date', 'int', or 'bool')
        """
        declarations = {}
        # Pattern to match variable declarations: "variable_name: type"
        # where type is date, int, or bool
        declaration_pattern = r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$"

        for constraint in constraints:
            constraint = constraint.strip()
            match = re.match(declaration_pattern, constraint, re.IGNORECASE)
            if match:
                var_name = match.group(1)
                var_type = match.group(2).lower()  # Normalize to lowercase
                if var_type in ["date", "int", "bool"]:
                    declarations[var_name] = var_type

        return declarations

    def filter_declarations_from_constraints(self, constraints: List[str]) -> List[str]:
        """
        Filter out variable declarations from the constraints list.

        Args:
            constraints: List of constraint strings

        Returns:
            Filtered list with declarations removed
        """
        filtered = []
        declaration_pattern = r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$"

        for constraint in constraints:
            constraint = constraint.strip()
            if not re.match(declaration_pattern, constraint, re.IGNORECASE):
                filtered.append(constraint)

        return filtered

    def extract_variables_from_constraints(self, constraints: List[str]) -> List[str]:
        """
        Extract all variable names from constraints.

        Args:
            constraints: List of constraint strings

        Returns:
            Sorted list of unique variable names found in constraints
        """
        variables = set()

        for constraint in constraints:
            # Remove property access patterns (var.property) to avoid
            # extracting property names as variables
            # Replace patterns like ".year", ".month", ".day" with empty string
            cleaned_constraint = re.sub(r"\.(?:year|month|day)\b", "", constraint)

            # Find all potential variable names using regex
            # This matches CNAME pattern: [a-zA-Z_][a-zA-Z0-9_]*
            var_matches = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", cleaned_constraint)

            for match in var_matches:
                # Filter out keywords and constructors
                if match not in [
                    "Date",
                    "Period",
                    "And",
                    "Or",
                    "Not",
                    "Implies",
                    "and",
                    "or",
                    "not",
                    "True",
                    "False",
                ]:
                    variables.add(match)

        return sorted(list(variables))

    def infer_variable_types_from_context(
        self, constraints: List[str], skip_declared: Dict[str, str] = None
    ) -> Dict[str, str]:
        """
        Infer variable types from their usage context in constraints using the parse tree.

        This method parses each constraint and walks the parse tree to infer types:
        - Variables in date_expr context → 'date'
        - Variables in int_expr context → 'int'
        - Variables in bool_expr context (standalone) → 'bool'
        - Variables in Date()/Period() constructors → 'int'

        Args:
            constraints: List of constraint strings
            skip_declared: Dictionary of already-declared variables to skip inference for

        Returns:
            Dictionary mapping inferred variable names to their types (excludes skip_declared vars)
        """
        inferred_types = {}
        skip_declared = skip_declared or {}

        for constraint in constraints:
            try:
                # Parse the constraint to get the tree structure
                tree = self.parser.parse(constraint)

                # Walk the tree to infer variable types from context
                self._infer_types_from_tree(tree, inferred_types, skip_declared)

            except Exception:
                # If parsing fails, fall back to regex-based inference for Date() args
                # Find variables inside Date() constructor arguments
                date_pattern = (
                    r"Date\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)"
                )
                date_matches = re.finditer(date_pattern, constraint)
                for match in date_matches:
                    for arg in [match.group(1), match.group(2), match.group(3)]:
                        var_names = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", arg)
                        for var_name in var_names:
                            if var_name not in [
                                "Date",
                                "Period",
                                "And",
                                "Or",
                                "Not",
                                "Implies",
                                "and",
                                "or",
                                "not",
                                "True",
                                "False",
                                "year",
                                "month",
                                "day",
                            ]:
                                if var_name not in skip_declared:
                                    property_access_pattern = rf"\b{re.escape(var_name)}\s*\.\s*(?:year|month|day)\b"
                                    if not re.search(property_access_pattern, arg):
                                        inferred_types[var_name] = "int"

        return inferred_types

    def _validate_parse_tree_types(self, tree, variable_types: Dict[str, str]) -> None:
        """
        Validate that the parse tree is consistent with declared variable types.

        This is called after parsing but before transformation to reject ambiguous
        parses that don't match declared types.

        Args:
            tree: Lark parse tree
            variable_types: Dictionary of declared variable types

        Raises:
            ValueError: If declared types conflict with parse tree structure
        """
        from lark import Token, Tree

        if isinstance(tree, Token):
            return

        if not isinstance(tree, Tree):
            return

        rule = tree.data

        # Check comparisons for type consistency
        if rule in ["date_comparison", "int_comparison"]:
            # Collect all declared variables and check for mixed types or concrete type indicators
            declared_vars = []
            has_date_literal = False
            has_int_literal = False

            for child in tree.children:
                if isinstance(child, Tree):
                    if child.data == "variable":
                        var_name = str(child.children[0])
                        if var_name in variable_types:
                            declared_vars.append((var_name, variable_types[var_name]))
                    elif child.data == "date_constructor":
                        has_date_literal = True
                    elif child.data == "int_const":
                        has_int_literal = True

            # If there are concrete literals, enforce strict type matching
            if has_date_literal:
                # Date literal present - all variables must be date type
                for var_name, var_type in declared_vars:
                    if var_type != "date":
                        raise ValueError(
                            f"Type error: Cannot compare {var_type} variable '{var_name}' with Date literal"
                        )
            elif has_int_literal:
                # Int literal present - all variables must be int/bool type
                for var_name, var_type in declared_vars:
                    if var_type not in ["int", "bool"]:
                        raise ValueError(
                            f"Type error: Cannot compare {var_type} variable '{var_name}' with integer literal"
                        )

            # If only variables (no literals), check they're all the same type
            elif len(declared_vars) >= 2:
                first_type = declared_vars[0][1]
                for var_name, var_type in declared_vars[1:]:
                    if var_type != first_type:
                        raise ValueError(
                            f"Type error: Cannot compare {first_type} variable '{declared_vars[0][0]}' "
                            f"with {var_type} variable '{var_name}'"
                        )

            # Recurse into children
            for child in tree.children:
                if isinstance(child, Tree):
                    self._validate_parse_tree_types(child, variable_types)

        # Recurse into all children
        else:
            for child in tree.children:
                if isinstance(child, Tree):
                    self._validate_parse_tree_types(child, variable_types)

    def _infer_types_from_tree(
        self, tree, inferred_types: Dict[str, str], skip_declared: Dict[str, str] = None
    ) -> None:
        """
        Walk the parse tree and infer variable types from their context.

        Args:
            tree: Lark parse tree node
            inferred_types: Dictionary to populate with inferred types
            skip_declared: Dictionary of already-declared variables to skip
        """
        from lark import Token, Tree

        skip_declared = skip_declared or {}

        if isinstance(tree, Token):
            return

        if not isinstance(tree, Tree):
            return

        # Check the rule name to determine context
        rule = tree.data

        # Handle date comparisons - all variables must be dates
        if rule == "date_comparison":
            for child in tree.children:
                if isinstance(child, Tree):
                    if child.data == "variable":
                        var_name = str(child.children[0])
                        # Skip True/False as they're boolean literals, not variables
                        if var_name in ["True", "False"]:
                            continue
                        # Skip already-declared variables
                        if var_name in skip_declared:
                            continue
                        if var_name not in inferred_types:
                            inferred_types[var_name] = "date"
                    else:
                        # Recurse to handle nested expressions
                        self._infer_types_from_tree(
                            child, inferred_types, skip_declared
                        )
            return

        # Handle int comparisons - all variables must be ints (or check for bool literals)
        if rule == "int_comparison":
            # Check for boolean literals in int comparisons (e.g., x == True)
            has_bool_literal = any(
                isinstance(child, Tree)
                and (
                    (
                        child.data == "variable"
                        and str(child.children[0]) in ["True", "False"]
                    )
                    or child.data == "bool_literal"
                )
                for child in tree.children
            )

            for child in tree.children:
                if isinstance(child, Tree):
                    if child.data == "variable":
                        var_name = str(child.children[0])
                        # Skip True/False as they're boolean literals, not variables
                        if var_name in ["True", "False"]:
                            continue
                        # Skip already-declared variables
                        if var_name in skip_declared:
                            continue
                        if var_name not in inferred_types:
                            # If comparing with bool literal, infer as bool
                            if has_bool_literal:
                                inferred_types[var_name] = "bool"
                            else:
                                inferred_types[var_name] = "int"
                    else:
                        # Recurse to handle nested expressions
                        self._infer_types_from_tree(
                            child, inferred_types, skip_declared
                        )
            return

        # Variables in date expressions
        if rule in ["date_expr", "date_atom", "date_add_period", "date_sub_period"]:
            for child in tree.children:
                if isinstance(child, Tree) and child.data == "variable":
                    var_name = str(child.children[0])
                    # Skip True/False as they're boolean literals
                    if var_name in ["True", "False"]:
                        continue
                    if var_name not in inferred_types:
                        inferred_types[var_name] = "date"

        # Variables in integer expressions
        elif rule in [
            "int_expr",
            "int_term",
            "int_atom",
            "int_add",
            "int_sub",
            "int_mul",
            "int_neg",
        ]:
            for child in tree.children:
                if isinstance(child, Tree) and child.data == "variable":
                    var_name = str(child.children[0])
                    # Skip True/False as they're boolean literals
                    if var_name in ["True", "False"]:
                        continue
                    # Only infer as int if not already inferred as date
                    if var_name not in inferred_types:
                        inferred_types[var_name] = "int"

        # Variables in Date/Period constructors are always int
        elif rule in ["date_constructor", "period_constructor"]:
            for child in tree.children:
                if isinstance(child, Tree):
                    self._extract_vars_as_int(child, inferred_types)

        # Date field access (k.year, k.month, k.day)
        elif rule == "date_field_access":
            # Variable with property access is a date
            for child in tree.children:
                if isinstance(child, Tree) and child.data == "variable":
                    var_name = str(child.children[0])
                    # Skip True/False as they're boolean literals
                    if var_name in ["True", "False"]:
                        continue
                    if var_name not in inferred_types:
                        inferred_types[var_name] = "date"

        # Standalone boolean variables (at constraint level)
        elif rule == "constraint":
            # Check if this is just a standalone variable (bool)
            if len(tree.children) == 1:
                child = tree.children[0]
                if isinstance(child, Tree) and child.data == "variable":
                    var_name = str(child.children[0])
                    # Skip True/False as they're boolean literals
                    if var_name in ["True", "False"]:
                        pass  # Don't infer
                    elif var_name not in inferred_types:
                        inferred_types[var_name] = "bool"

        # Recurse into children
        for child in tree.children:
            if isinstance(child, Tree):
                self._infer_types_from_tree(child, inferred_types, skip_declared)

    def _extract_vars_as_int(self, tree, inferred_types: Dict[str, str]) -> None:
        """Extract all variables in a subtree as 'int' type.

        Skip variables that are part of date_field_access (e.g., x in x.year),
        as those should remain as date type.
        """
        from lark import Token, Tree

        if isinstance(tree, Token):
            return

        if isinstance(tree, Tree):
            # Skip date_field_access nodes - the variable in x.year should remain a date
            if tree.data == "date_field_access":
                return

            if tree.data == "variable":
                var_name = str(tree.children[0])
                # Skip True/False as they're boolean literals
                if var_name not in ["True", "False"]:
                    inferred_types[var_name] = "int"

            for child in tree.children:
                if isinstance(child, Tree):
                    self._extract_vars_as_int(child, inferred_types)

    def infer_date_component_bounds(self, constraints: List[str]) -> Dict[str, str]:
        """
        Infer which Date() component position each integer expression is used in.

        This allows us to automatically add appropriate bounds constraints:
        - Position 1 (year): 1900 <= expr <= 2100
        - Position 2 (month): 1 <= expr <= 12
        - Position 3 (day): 1 <= expr <= 31

        For example, Date(x+2000, 1, 1) will generate:
        - (x + 2000) >= 1900
        - (x + 2000) <= 2100

        Args:
            constraints: List of constraint strings

        Returns:
            Dictionary mapping expressions to their component type ('year', 'month', 'day', or 'mixed')
            'mixed' means the expression is used in multiple positions
        """
        component_usage = {}  # expr -> set of component types

        for constraint in constraints:
            # Find Date() constructors and their arguments
            date_pattern = r"Date\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)"
            date_matches = re.finditer(date_pattern, constraint)

            for match in date_matches:
                args = [
                    match.group(1).strip(),
                    match.group(2).strip(),
                    match.group(3).strip(),
                ]
                component_types = ["year", "month", "day"]

                for arg, component_type in zip(args, component_types):
                    # Skip if this is a concrete constant (no variables)
                    has_variables = bool(re.search(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", arg))
                    if not has_variables:
                        continue

                    # Skip if this is a property access (e.g., x.year)
                    if re.search(
                        r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*\.\s*(?:year|month|day)\b", arg
                    ):
                        continue

                    # Check if the expression contains any keywords that should be excluded
                    expr_vars = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", arg)
                    if any(
                        v
                        in [
                            "Date",
                            "Period",
                            "And",
                            "Or",
                            "Not",
                            "Implies",
                            "and",
                            "or",
                            "not",
                            "True",
                            "False",
                            "year",
                            "month",
                            "day",
                        ]
                        for v in expr_vars
                    ):
                        continue

                    # Store the full expression (not just variable names)
                    if arg not in component_usage:
                        component_usage[arg] = set()
                    component_usage[arg].add(component_type)

        # Convert sets to single strings, or 'mixed' if used in multiple positions
        result = {}
        for expr, components in component_usage.items():
            if len(components) == 1:
                result[expr] = list(components)[0]
            else:
                result[expr] = "mixed"

        return result

    def _extract_and_replace_parametric_dates(
        self, constraints: List[str], variable_types: Dict[str, str]
    ) -> tuple[List[str], Dict[str, tuple[str, str, str]]]:
        """
        Extract parametric Date constructors and replace them with auxiliary variables.

        A parametric Date constructor has one or more variable arguments, e.g., Date(x.year, 2, 28).
        These need special handling because they can't be constructed directly at runtime.

        Args:
            constraints: List of constraint strings
            variable_types: Dictionary of declared variable types

        Returns:
            Tuple of (modified_constraints, parametric_dates_map)
            where parametric_dates_map is {aux_var_name: (year_expr, month_expr, day_expr)}
        """
        import re

        parametric_dates = {}  # aux_var -> (year, month, day)
        aux_counter = [0]  # Use list for mutability in nested function

        def replace_parametric_date(match):
            """Replace a parametric Date constructor with an auxiliary variable."""
            full_match = match.group(0)
            args = match.group(1)

            # Parse the three arguments
            # Simple comma splitting won't work due to nested expressions, so use a proper parser
            depth = 0
            current_arg = []
            parsed_args = []

            for char in args:
                if char == "(":
                    depth += 1
                    current_arg.append(char)
                elif char == ")":
                    depth -= 1
                    current_arg.append(char)
                elif char == "," and depth == 0:
                    parsed_args.append("".join(current_arg).strip())
                    current_arg = []
                else:
                    current_arg.append(char)

            if current_arg:
                parsed_args.append("".join(current_arg).strip())

            if len(parsed_args) != 3:
                return full_match  # Not a valid Date constructor

            year_expr, month_expr, day_expr = parsed_args

            # Check if any argument contains a variable (not just constants)
            has_variable = (
                ConstraintTransformer._has_variable(year_expr)
                or ConstraintTransformer._has_variable(month_expr)
                or ConstraintTransformer._has_variable(day_expr)
            )

            if not has_variable:
                # All concrete - no transformation needed
                return full_match

            # This is a parametric Date - create an auxiliary variable
            aux_var = f"_aux_date_{aux_counter[0]}"
            aux_counter[0] += 1

            parametric_dates[aux_var] = (year_expr, month_expr, day_expr)

            return aux_var

        # Pattern to match Date(...) constructors
        # This matches Date( followed by balanced parentheses
        date_pattern = r"Date\(([^)]+(?:\([^)]*\)[^)]*)*)\)"

        modified_constraints = []
        for constraint in constraints:
            # Replace all parametric Date constructors in this constraint
            modified = re.sub(date_pattern, replace_parametric_date, constraint)
            modified_constraints.append(modified)

        return modified_constraints, parametric_dates

    def generate_builder_code(
        self,
        constraints: List[str],
        declarations: List[str] = None,
    ) -> str:
        """
        Generate complete DateSMTBuilder code from structured constraint data.

        Each constraint is a full boolean expression that can include:
        - Comparisons: x >= Date(2000,2,28)
        - Boolean operators: && (and), || (or), ! (not)
        - Implications: (A) -> (B)
        - Nested expressions: ((a || b) || c) || d
        - Parametric Date constructors: Date(x.year, 2, 28) in any context

        All constraints in the list are ANDed together.

        Variable declarations can be provided separately via the `declarations` parameter,
        or mixed in with constraints (backward compatibility). All variables used in constraints
        must be explicitly declared.

        Args:
            constraints: List of constraint strings (each is a full boolean expression)
            declarations: Optional list of variable declarations like ["x: date", "y: int"].
                         If provided, declarations are not extracted from constraints.

        Returns:
            Complete Python code string

        Raises:
            ValueError: If any variable used in constraints is not explicitly declared
        """
        code_lines = [
            "from z3 import Or, And, Not, Int, Bool, Implies",
            "builder = DateSMTBuilder()",
            "",
        ]

        # Extract variable declarations
        if declarations is not None:
            # New format: declarations provided separately
            variable_types = self.extract_variable_declarations(declarations)
            filtered_constraints = (
                constraints  # No need to filter, constraints don't contain declarations
            )
        else:
            # Old format: declarations mixed with constraints (backward compatibility)
            variable_types = self.extract_variable_declarations(constraints)
            filtered_constraints = self.filter_declarations_from_constraints(
                constraints
            )

        self.variable_types = variable_types

        # Validate parentheses balance in all constraints FIRST (before any other validation)
        for constraint in filtered_constraints:
            self._validate_parentheses_balance(constraint)

        # Auto-extract variables from remaining constraints
        # We extract from ORIGINAL constraints (before transformation) to capture
        # variables inside parametric Date constructors for type inference
        all_variables = self.extract_variables_from_constraints(filtered_constraints)

        # Check for common mistakes: lowercase boolean literals (before type inference)
        lowercase_bools = {"true": "True", "false": "False"}
        bool_mistakes = [var for var in all_variables if var in lowercase_bools]
        if bool_mistakes:
            corrections = [
                f"'{var}' should be '{lowercase_bools[var]}'" for var in bool_mistakes
            ]
            raise ValueError(
                f"Invalid boolean literal(s): {', '.join(corrections)}. "
                f"Python uses capitalized 'True' and 'False' for boolean values."
            )

        # Infer types for undeclared variables from their usage context
        # Skip inference for already-declared variables to avoid conflicts
        inferred_types = self.infer_variable_types_from_context(
            filtered_constraints, skip_declared=variable_types
        )

        # Check for type conflicts between explicit declarations and inferred usage
        # This catches cases where a variable is declared one type but used as another
        type_conflicts = []
        for var_name, inferred_type in inferred_types.items():
            if var_name in variable_types:
                declared_type = variable_types[var_name]
                if declared_type != inferred_type:
                    type_conflicts.append((var_name, declared_type, inferred_type))

        if type_conflicts:
            conflict_messages = []
            for var_name, declared_type, inferred_type in type_conflicts:
                conflict_messages.append(
                    f"'{var_name}' is declared as '{declared_type}' but inferred as '{inferred_type}' from usage context"
                )
            raise ValueError(
                f"Type conflict detected:\n  - " + "\n  - ".join(conflict_messages)
            )

        # Merge inferred types into variable_types (explicit declarations take precedence)
        for var_name, var_type in inferred_types.items():
            if var_name not in variable_types:
                variable_types[var_name] = var_type

        # Check for undeclared variables that couldn't be inferred
        undeclared_vars = [var for var in all_variables if var not in variable_types]
        if undeclared_vars:
            # For undeclared variables, use inferred types
            # This allows the parser to continue with best-effort type inference
            for var in undeclared_vars:
                if var in inferred_types:
                    variable_types[var] = inferred_types[var]

            # Check if there are still undeclared variables after inference
            still_undeclared = [
                var for var in undeclared_vars if var not in variable_types
            ]
            if still_undeclared:
                undeclared_str = ", ".join(sorted(still_undeclared))
                raise ValueError(
                    f"Could not infer types for variables: {undeclared_str}. "
                    f"Please explicitly declare them using 'variable_name: type' syntax "
                    f"(where type is 'date', 'int', or 'bool')."
                )

        # Infer bounds for integer variables used in Date() constructors
        component_bounds = self.infer_date_component_bounds(filtered_constraints)

        # Add variable declarations
        for var_name, var_type in sorted(variable_types.items()):
            if var_type == "date":
                code_lines.append(f'{var_name} = builder.add_date_var("{var_name}")')
            elif var_type == "int":
                # Create int variables without bounds - bounds will be added as constraints
                code_lines.append(f'{var_name} = builder.add_int_var("{var_name}")')
            elif var_type == "bool":
                code_lines.append(f'{var_name} = builder.add_bool_var("{var_name}")')

        # Add natural bounds constraints for integer expressions used in Date() constructors
        # Only add bounds for non-constant expressions (variables or complex expressions)
        if component_bounds:
            # Filter out constant numbers - they don't need bounds
            non_constant_bounds = {
                expr: comp_type
                for expr, comp_type in component_bounds.items()
                if not expr.lstrip(
                    "-"
                ).isdigit()  # Skip if it's a plain number like "2020" or "-5"
            }

            if non_constant_bounds:
                code_lines.append("")
                code_lines.append("# Automatic bounds for Date() component expressions")
                for expr, component_type in sorted(non_constant_bounds.items()):
                    # Wrap complex expressions in parentheses for safety
                    if any(op in expr for op in ["+", "-", "*"]):
                        expr_wrapped = f"({expr})"
                    else:
                        expr_wrapped = expr

                    if component_type == "year":
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} >= 1900)"
                        )
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} <= 2100)"
                        )
                    elif component_type == "month":
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} >= 1)"
                        )
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} <= 12)"
                        )
                    elif component_type == "day":
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} >= 1)"
                        )
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} <= 31)"
                        )
                    elif component_type == "mixed":
                        # Expression used in multiple positions - use most restrictive bounds
                        code_lines.append(
                            f"# Warning: {expr} used in multiple Date() positions - using conservative bounds"
                        )
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} >= 1)"
                        )
                        code_lines.append(
                            f"builder.add_constraint({expr_wrapped} <= 2100)"
                        )

        # STEP: Transform parametric Date constructors AFTER type inference and bounds checking
        # This must happen before parsing to avoid runtime errors
        transformed_constraints, parametric_dates = (
            self._extract_and_replace_parametric_dates(
                filtered_constraints, variable_types
            )
        )

        # Add auxiliary date variables to variable_types
        for aux_var in parametric_dates:
            variable_types[aux_var] = "date"

        # Add variable declarations for auxiliary date variables
        for aux_var in sorted(parametric_dates.keys()):
            code_lines.append(f'{aux_var} = builder.add_date_var("{aux_var}")')

        # Add constraints for parametric Date constructors (auxiliary variables)
        if parametric_dates:
            code_lines.append("")
            code_lines.append("# Constraints for parametric Date constructors")
            for aux_var, (year_expr, month_expr, day_expr) in sorted(
                parametric_dates.items()
            ):
                # Generate component-wise constraints: aux_var.year == year_expr, etc.
                code_lines.append(
                    f"builder.add_constraint({aux_var}.year == {year_expr})"
                )
                code_lines.append(
                    f"builder.add_constraint({aux_var}.month == {month_expr})"
                )
                code_lines.append(
                    f"builder.add_constraint({aux_var}.day == {day_expr})"
                )

        # Add constraints (using TRANSFORMED constraints)
        # Each constraint is a full boolean expression - parse and add directly
        code_lines.append("")
        for constraint_str in transformed_constraints:
            constraint_code = self.parse_constraint(constraint_str, variable_types)
            code_lines.append(constraint_code)

        return "\n".join(code_lines)

    def parse_constraint_data(self, constraint_data: Dict[str, Any]) -> str:
        """
        Parse constraint data and return executable code.

        Supports two formats:
        1. New format (recommended): Separate 'declarations' and 'constraints' fields
           {
             "declarations": ["x: date", "y: int"],
             "constraints": ["x >= Date(2000,2,28)", "(a || b) && c"]
           }

        2. Old format (backward compatible): Declarations mixed with constraints
           {
             "constraints": ["x: date", "x >= Date(2000,2,28)", "(a || b) && c"]
           }

        Each constraint is a full boolean expression that can include:
        - Comparisons: x >= Date(2000,2,28)
        - Boolean operators: && (and), || (or), ! (not)
        - Implications: (A) -> (B)
        - Nested expressions: ((a || b) || c) || d

        All constraints in the list are ANDed together.

        Args:
            constraint_data: Dictionary with:
                - 'constraints': List of constraint strings (required)
                - 'declarations': Optional list of variable declarations (new format)

        Returns:
            Executable Python code string
        """
        constraints = constraint_data.get("constraints", [])
        declarations = constraint_data.get("declarations", None)

        # Ensure constraints is a list of strings (no nested lists)
        for constraint in constraints:
            if isinstance(constraint, list):
                raise ValueError(
                    "Nested lists are not supported. Each constraint must be a string with boolean operators."
                )

        # If declarations provided, ensure it's also a list of strings
        if declarations is not None:
            for declaration in declarations:
                if isinstance(declaration, list):
                    raise ValueError(
                        "Nested lists are not supported. Each declaration must be a string like 'x: date'."
                    )
                if not isinstance(declaration, str):
                    raise ValueError(
                        f"Invalid declaration format: {declaration}. Expected string like 'x: date'."
                    )

        return self.generate_builder_code(constraints, declarations)
