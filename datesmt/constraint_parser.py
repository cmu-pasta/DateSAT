"""
Constraint parser for Date-SMT system.

This module provides functionality to parse constraints from the structured format
and convert them into executable DateSMTBuilder code.
"""

import re
from typing import Any, Dict, List, Tuple

from .core import Date, Period


class ConstraintParser:
    """Parser for structured constraint format."""

    def __init__(self):
        self.date_vars: Dict[str, Any] = {}
        self.period_vars: Dict[str, Any] = {}

    def parse_constraint(self, constraint_str: str) -> str:
        """
        Parse a single constraint string and return the corresponding Python code.

        Args:
            constraint_str: Constraint string like "x>=Date(2000,2,28)"

        Returns:
            Python code string for the constraint
        """
        # Remove comments (anything after a comma followed by a quote)
        if ',' in constraint_str and "'" in constraint_str:
            # Find the last comma followed by a quote
            comma_pos = constraint_str.rfind(',')
            if comma_pos != -1 and "'" in constraint_str[comma_pos:]:
                constraint_str = constraint_str[:comma_pos]

        # Remove whitespace
        constraint_str = constraint_str.strip()

        # Parse comparison operators
        operators = ['>=', '<=', '==', '!=', '>', '<']
        for op in operators:
            if op in constraint_str:
                left, right = constraint_str.split(op, 1)
                left = left.strip()
                right = right.strip()

                # Parse left side (variable)
                left_code = self._parse_expression(left)

                # Parse right side (value or expression)
                right_code = self._parse_expression(right)

                return f"builder.add_constraint({left_code} {op} {right_code})"

        raise ValueError(f"Could not parse constraint: {constraint_str}")

    def _parse_expression(self, expr: str) -> str:
        """Parse an expression (variable, Date, Period, or arithmetic)."""
        expr = expr.strip()

        # Handle Date constructor
        if expr.startswith('Date('):
            return expr

        # Handle Period constructor
        if expr.startswith('Period('):
            return expr

        # Handle arithmetic expressions (e.g., "x + Period(0,1,0)")
        if '+' in expr or '-' in expr:
            return self._parse_arithmetic_expression(expr)

        # Handle parentheses for grouping
        if expr.startswith('(') and expr.endswith(')'):
            inner = expr[1:-1].strip()
            return f"({self._parse_expression(inner)})"

        # Handle simple variable names
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', expr):
            return expr

        raise ValueError(f"Could not parse expression: {expr}")

    def _parse_arithmetic_expression(self, expr: str) -> str:
        """Parse arithmetic expressions like 'x + Period(0,1,0)' or 'p + q - Period(0,0,5)'."""
        # Parse from right to left to handle operator precedence correctly
        # This handles expressions like "a + b - c" by parsing as "a + (b - c)"

        # Find the rightmost + or - that's not inside parentheses
        paren_count = 0
        for i in range(len(expr) - 1, -1, -1):
            char = expr[i]
            if char == ')':
                paren_count += 1
            elif char == '(':
                paren_count -= 1
            elif char in '+-' and paren_count == 0:
                left = expr[:i].strip()
                right = expr[i + 1 :].strip()
                op = char

                left_code = self._parse_arithmetic_expression(left)
                right_code = self._parse_arithmetic_expression(right)
                return f"{left_code} {op} {right_code}"

        # If no operator found, treat as single expression
        return self._parse_simple_expression(expr)

    def _parse_simple_expression(self, expr: str) -> str:
        """Parse simple expressions without arithmetic operators."""
        expr = expr.strip()

        # Handle Date() constructor
        if expr.startswith('Date('):
            return expr

        # Handle Period() constructor
        if expr.startswith('Period('):
            return expr

        # Handle parentheses for grouping - check if inner content has arithmetic
        if expr.startswith('(') and expr.endswith(')'):
            inner = expr[1:-1].strip()
            # If inner content has arithmetic operators, use arithmetic parsing
            if '+' in inner or '-' in inner:
                return f"({self._parse_arithmetic_expression(inner)})"
            else:
                return f"({self._parse_simple_expression(inner)})"

        # Handle simple variable names
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', expr):
            return expr

        raise ValueError(f"Could not parse simple expression: {expr}")

    def generate_builder_code(
        self,
        constraints: List[str],
        date_variables: List[str],
        period_variables: List[str],
    ) -> str:
        """
        Generate complete DateSMTBuilder code from structured constraint data.

        Args:
            constraints: List of constraint strings
            date_variables: List of date variable names
            period_variables: List of period variable names

        Returns:
            Complete Python code string
        """
        code_lines = ["builder = DateSMTBuilder()"]

        # Add date variables
        for var_name in date_variables:
            code_lines.append(f'{var_name} = builder.add_date_var("{var_name}")')

        # Add period variables
        for var_name in period_variables:
            code_lines.append(f'{var_name} = builder.add_period_var("{var_name}")')

        # Add constraints
        for constraint in constraints:
            constraint_code = self.parse_constraint(constraint)
            code_lines.append(constraint_code)

        # Add result assignment
        code_lines.append("result = builder")

        return "\n".join(code_lines)

    def parse_constraint_data(self, constraint_data: Dict[str, Any]) -> str:
        """
        Parse constraint data in the new format and return executable code.

        Args:
            constraint_data: Dictionary with 'constraints', 'date_variables', 'period_variables'

        Returns:
            Executable Python code string
        """
        constraints = constraint_data.get('constraints', [])
        date_variables = constraint_data.get('date_variables', [])
        period_variables = constraint_data.get('period_variables', [])

        return self.generate_builder_code(constraints, date_variables, period_variables)
