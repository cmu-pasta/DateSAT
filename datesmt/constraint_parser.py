"""
Constraint parser for Date-SMT system using Lark parser generator.

This module provides functionality to parse constraints from the structured format
and convert them into executable DateSMTBuilder code using a context-free grammar.
"""

from typing import Any, Dict, List, Union
from lark import Lark, Transformer
import re


class ConstraintTransformer(Transformer):
    """Transformer to convert Lark parse tree to Python code."""
    
    def top_level_constraint(self, items) -> str:
        """Transform a top-level constraint."""
        bool_expr = items[0]
        
        # Check if bool_expr already has builder.add_constraint wrapper (from implication)
        if bool_expr.startswith("builder.add_constraint("):
            return bool_expr
        
        return f"builder.add_constraint({bool_expr})"
    
    def implication(self, items) -> str:
        """Transform implication (A) -> (B) into Implies(A, B). Supports nesting."""
        # items = [antecedent, IMPLIES token, consequent]
        antecedent = items[0]
        consequent = items[2]
        # Return just the Implies expression, wrapping is done by top_level_constraint
        return f"Implies({antecedent}, {consequent})"
    
    def comparison_expr(self, items) -> str:
        """Transform a comparison expression (left op right)."""
        left, op, right = items
        
        # Check if we need to transform parametric Date() comparisons
        # (Date constructors with variable arguments, e.g., Date(x, 2, 1))
        transformed = self._transform_parametric_date_comparison(left, op, right)
        if transformed:
            return transformed
        return f"{left} {op} {right}"
    
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
        date_start = expr.find('Date(')
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
            if char == '(':
                paren_count += 1
                current_arg.append(char)
            elif char == ')':
                if paren_count == 0:
                    # This is the closing paren for Date()
                    if current_arg:
                        args.append(''.join(current_arg).strip())
                    break
                paren_count -= 1
                current_arg.append(char)
            elif char == ',' and paren_count == 0:
                # This comma separates arguments
                args.append(''.join(current_arg).strip())
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
        if re.match(r'^-?\d+$', expr):
            return False
        # If it contains identifier characters, it has a variable
        return bool(re.search(r'[a-zA-Z_][a-zA-Z0-9_]*', expr))

    def _transform_parametric_date_comparison(self, left: str, op: str, right: str) -> str:
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
        if not (self._has_variable(year_expr) or self._has_variable(month_expr) or self._has_variable(day_expr)):
            return None
        
        # Extract the date variable name (handle property access like x.year)
        date_var_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', date_var_expr)
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
            "!=": "!="
        }
        return inversions.get(op, op)
    
    def expression(self, items) -> str:
        """Handle expression precedence."""
        if len(items) == 1:
            return items[0]
        # This handles operator precedence automatically
        return " ".join(str(item) for item in items)
    
    def add(self, items) -> str:
        """Transform addition operation."""
        left, right = items
        return f"{left} + {right}"
    
    def sub(self, items) -> str:
        """Transform subtraction operation."""
        left, right = items
        return f"{left} - {right}"
    
    def mul(self, items) -> str:
        """Transform multiplication operation."""
        left, right = items
        return f"{left} * {right}"
    
    def term(self, items) -> str:
        """Handle term precedence."""
        if len(items) == 1:
            return items[0]
        return " ".join(str(item) for item in items)
    
    def factor(self, items) -> str:
        """Handle factor grouping."""
        if len(items) == 1:
            return items[0]
        return " ".join(str(item) for item in items)
    
    def parenthesized_expression(self, items) -> str:
        """Transform parenthesized expression."""
        if len(items) == 3:
            return f"({items[1]})"
        return " ".join(str(item) for item in items)
    
    def parenthesized_bool_expr(self, items) -> str:
        """Transform parenthesized boolean expression (comparison)."""
        # items = [LPAR, comparison_expr, RPAR]
        if len(items) == 3:
            return f"({items[1]})"
        return f"({items[0]})"
    
    def variable(self, items) -> str:
        """Transform variable reference."""
        return str(items[0])
    
    def property_access(self, items) -> str:
        """Transform property access like x.year, x.month, x.day."""
        var_name, property_name = items
        return f"{var_name}.{property_name}"
    
    def date_property_access(self, items) -> str:
        """Transform property access on Date constructor like Date(1991,2,3).month."""
        date_expr, property_name = items
        return f"{date_expr}.{property_name}"
    
    def property_name(self, items) -> str:
        """Transform property name."""
        return str(items[0])
    
    def date_constructor(self, items) -> str:
        """Transform Date constructor (may contain symbolic expressions)."""
        year, month, day = items
        return f"Date({year}, {month}, {day})"
    
    def period_constructor(self, items) -> str:
        """Transform Period constructor."""
        years, months, days = items
        return f"Period({years}, {months}, {days})"
    
    def comparison_op(self, items) -> str:
        """Transform comparison operator."""
        if not items:
            return ""
        return str(items[0])
    
    def number(self, items) -> str:
        """Transform number literal."""
        return str(items[0])
    
    def string(self, items) -> str:
        """Transform string literal."""
        return str(items[0])
    


class ConstraintParser:
    """Parser for structured constraint format using Lark grammar."""

    def __init__(self):
        """Initialize the parser with Lark grammar."""
        self.variable_types: Dict[str, str] = {}  # Maps variable name to type: 'date', 'int', or 'bool'
        
        # Define the grammar for constraint parsing
        self.grammar = """
            ?constraint: top_level_constraint
            
            top_level_constraint: bool_expr
            ?bool_expr: implication | comparison_expr
            implication: "(" bool_expr ")" IMPLIES "(" bool_expr ")"
            comparison_expr: expression comparison_op expression
            
            IMPLIES: "->"
            
            ?expression: term
                       | expression "+" term -> add
                       | expression "-" term -> sub
            
            ?term: factor
                 | term "*" factor -> mul
                 | term "/" factor -> div
            
            ?factor: variable
                   | date_constructor
                   | period_constructor
                   | number
                   | parenthesized_expression
                   | parenthesized_bool_expr
                   | property_access
                   | date_property_access
                   | bool_literal
            
            parenthesized_expression: LPAR expression RPAR
            parenthesized_bool_expr: LPAR comparison_expr RPAR
            property_access: variable "." property_name
            date_property_access: date_constructor "." property_name
            
            LPAR: "("
            RPAR: ")"
            DOT: "."
            
            variable: CNAME
            property_name: PROPERTY_NAME
            PROPERTY_NAME: "year" | "month" | "day"
            bool_literal: BOOL_LITERAL
            BOOL_LITERAL: "True" | "False"
            date_constructor: "Date" "(" expression "," expression "," expression ")"
            period_constructor: "Period" "(" number "," number "," number ")"
            
            comparison_op: GTE | LTE | EQ | NE | GT | LT
            
            GTE: ">="
            LTE: "<="
            EQ: "=="
            NE: "!="
            GT: ">"
            LT: "<"
            
            number: SIGNED_NUMBER
            
            %import common.CNAME
            %import common.SIGNED_NUMBER
            %import common.WS
            %ignore WS
        """
        
        # Create the Lark parser with Earley algorithm to handle grammar ambiguity
        # (LALR can't handle the ambiguity between parenthesized_bool_expr and implication)
        self.parser = Lark(
            self.grammar, 
            parser='earley',
            ambiguity='resolve',
            start='constraint'
        )
        self.transformer = ConstraintTransformer()

    def parse_constraint(self, constraint_str: str) -> str:
        """
        Parse a single constraint string and return the corresponding Python code.

        Args:
            constraint_str: Constraint string like "x>=Date(2000,2,28)"

        Returns:
            Python code string for the constraint
        """
        # Remove whitespace
        constraint_str = constraint_str.strip()

        # Check for common unsupported patterns and give helpful error messages
        self._check_unsupported_patterns(constraint_str)

        # Check for invalid variable names that should raise ValueError
        if self._is_invalid_variable_name(constraint_str):
            raise ValueError(f"Could not parse constraint '{constraint_str}': Invalid variable name")
        try:
            # Parse using Lark and apply transformer
            tree = self.parser.parse(constraint_str)
            result = self.transformer.transform(tree)
            return result
        except Exception as e:
            raise ValueError(f"Could not parse constraint '{constraint_str}': {e}")
    
    def _check_unsupported_patterns(self, constraint_str: str) -> None:
        """Check for common unsupported patterns and raise helpful error messages."""
        # Check for && operator
        if '&&' in constraint_str:
            raise ValueError(
                f"'&&' operator is not supported. Use nested implications instead. "
                f"For 'if A and B then C', write: (A) -> ((B) -> (C))"
            )
        
        # Check for || operator
        if '||' in constraint_str:
            raise ValueError(
                f"'||' operator is not supported. Use CNF format (OR clauses as nested lists) instead. "
                f"For 'A or B', write: [[\"A\", \"B\"]]"
            )
    
    def _is_invalid_variable_name(self, constraint_str: str) -> bool:
        """Check if the constraint contains invalid variable names."""
        # Handle empty or whitespace-only strings
        if not constraint_str or constraint_str.isspace():
            return False
        
        # Property names that are valid after a dot
        valid_property_names = {'year', 'month', 'day'}
        
        # Check for invalid variable names like var-123, var.123, 123var
        # But exclude cases where hyphen/dot is followed by keywords like Period/Date or '('
        # This distinguishes "var-123" (invalid) from "z-Period(...)" (valid subtraction)
        pattern1 = r'\b[a-zA-Z_][a-zA-Z0-9_]*[-.][a-zA-Z0-9_]+\b'
        matches = re.finditer(pattern1, constraint_str)
        for match in matches:
            matched_text = match.group()
            # Check if the part after hyphen/dot is a keyword (Period, Date) or a property name
            parts = re.split(r'[-.]', matched_text, maxsplit=1)
            if len(parts) == 2:
                second_part = parts[1]
                # If it's a keyword or property name, this is valid
                if second_part in ['Period', 'Date'] or second_part in valid_property_names:
                    continue
                # Check if followed by '(' which would indicate a function call
                end_pos = match.end()
                if end_pos < len(constraint_str) and constraint_str[end_pos] == '(':
                    continue
                # Otherwise, it's an invalid variable name
                return True
        
        # Check for invalid variable names starting with digits like 123var
        if re.search(r'\b[0-9]+[a-zA-Z_][a-zA-Z0-9_]*\b', constraint_str):
            return True
        return False

    def extract_variable_declarations(self, constraints: List[Union[str, List[str]]]) -> Dict[str, str]:
        """
        Extract variable declarations from constraints.
        Looks for patterns like "x: date", "y: int", "z: bool".
        
        Args:
            constraints: List of constraint strings or lists of constraint strings
            
        Returns:
            Dictionary mapping variable names to their types ('date', 'int', or 'bool')
        """
        declarations = {}
        # Pattern to match variable declarations: "variable_name: type"
        # where type is date, int, or bool
        declaration_pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$'
        
        for constraint_item in constraints:
            # Handle both string and list formats
            if isinstance(constraint_item, list):
                constraint_strings = constraint_item
            else:
                constraint_strings = [constraint_item]
            
            for constraint in constraint_strings:
                constraint = constraint.strip()
                match = re.match(declaration_pattern, constraint, re.IGNORECASE)
                if match:
                    var_name = match.group(1)
                    var_type = match.group(2).lower()  # Normalize to lowercase
                    if var_type in ['date', 'int', 'bool']:
                        declarations[var_name] = var_type
        
        return declarations

    def filter_declarations_from_constraints(self, constraints: List[Union[str, List[str]]]) -> List[Union[str, List[str]]]:
        """
        Filter out variable declarations from the constraints list.
        
        Args:
            constraints: List of constraint strings or lists of constraint strings
            
        Returns:
            Filtered list with declarations removed
        """
        filtered = []
        declaration_pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$'
        
        for constraint_item in constraints:
            if isinstance(constraint_item, list):
                # Filter each item in the list
                filtered_list = []
                for constraint in constraint_item:
                    constraint = constraint.strip()
                    if not re.match(declaration_pattern, constraint, re.IGNORECASE):
                        filtered_list.append(constraint)
                if filtered_list:  # Only add non-empty lists
                    filtered.append(filtered_list)
            else:
                constraint = constraint_item.strip()
                if not re.match(declaration_pattern, constraint, re.IGNORECASE):
                    filtered.append(constraint)
        
        return filtered

    def extract_variables_from_constraints(self, constraints: List[Union[str, List[str]]]) -> List[str]:
        """
        Extract all variable names from constraints.
        
        Args:
            constraints: List of constraint strings or lists of constraint strings (for OR clauses)
            
        Returns:
            Sorted list of unique variable names found in constraints
        """
        variables = set()
        
        for constraint_item in constraints:
            # Handle both string and list formats
            if isinstance(constraint_item, list):
                # OR clause: extract variables from each constraint in the list
                constraint_strings = constraint_item
            else:
                # Single constraint
                constraint_strings = [constraint_item]
            
            for constraint in constraint_strings:
                # Remove property access patterns (var.property) to avoid
                # extracting property names as variables
                # Replace patterns like ".year", ".month", ".day" with empty string
                cleaned_constraint = re.sub(r'\.(?:year|month|day)\b', '', constraint)
                    
                # Find all potential variable names using regex
                # This matches CNAME pattern: [a-zA-Z_][a-zA-Z0-9_]*
                var_matches = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', cleaned_constraint)
                
                for match in var_matches:
                    # Filter out keywords and constructors
                    if match not in ['Date', 'Period', 'and', 'or', 'not', 'True', 'False']:
                        variables.add(match)
        
        return sorted(list(variables))
    
    def infer_variable_types_from_context(self, constraints: List[Union[str, List[str]]]) -> Dict[str, str]:
        """
        Infer variable types from their usage context in constraints.
        
        Variables used inside Date() or Period() constructors are inferred as 'int'.
        For all other cases, users must explicitly declare variable types.
        
        Args:
            constraints: List of constraint strings or lists of constraint strings
            
        Returns:
            Dictionary mapping inferred variable names to their types
        """
        inferred_types = {}
        
        for constraint_item in constraints:
            # Handle both string and list formats
            if isinstance(constraint_item, list):
                constraint_strings = constraint_item
            else:
                constraint_strings = [constraint_item]
            
            for constraint in constraint_strings:
                # Find variables inside Date() constructor arguments
                # Pattern: Date(arg1, arg2, arg3) where args can be expressions with variables
                date_pattern = r'Date\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)'
                date_matches = re.finditer(date_pattern, constraint)
                for match in date_matches:
                    for arg in [match.group(1), match.group(2), match.group(3)]:
                        # Extract variable names from each argument
                        var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', arg)
                        for var_name in var_names:
                            if var_name not in ['Date', 'Period', 'and', 'or', 'not', 'True', 'False']:
                                inferred_types[var_name] = 'int'
                
                # Find variables inside Period() constructor arguments
                period_pattern = r'Period\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)'
                period_matches = re.finditer(period_pattern, constraint)
                for match in period_matches:
                    for arg in [match.group(1), match.group(2), match.group(3)]:
                        # Extract variable names from each argument
                        var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', arg)
                        for var_name in var_names:
                            if var_name not in ['Date', 'Period', 'and', 'or', 'not', 'True', 'False']:
                                inferred_types[var_name] = 'int'
        
        return inferred_types

    def _check_comparison_type_mismatches(
        self, 
        constraints: List[Union[str, List[str]]], 
        variable_types: Dict[str, str]
    ) -> None:
        """
        Check for type mismatches in comparisons between variables.
        
        For example, comparing an int variable with a bool variable is invalid.
        """
        for constraint_item in constraints:
            if isinstance(constraint_item, list):
                constraint_strings = constraint_item
            else:
                constraint_strings = [constraint_item]
            
            for constraint in constraint_strings:
                # Find comparison operator and split
                comp_match = re.search(r'(==|!=|>=|<=|>|<)', constraint)
                if not comp_match:
                    continue
                
                op = comp_match.group(1)
                left_expr = constraint[:comp_match.start()].strip()
                right_expr = constraint[comp_match.end():].strip()
                
                # Get types for both sides
                left_type = self._get_full_expression_type(left_expr, variable_types)
                right_type = self._get_full_expression_type(right_expr, variable_types)
                
                if left_type is None or right_type is None:
                    continue
                
                if not self._types_compatible(left_type, right_type):
                    raise ValueError(
                        f"Type mismatch in constraint '{constraint}': "
                        f"cannot compare '{left_expr}' (type: {left_type}) with "
                        f"'{right_expr}' (type: {right_type}). "
                        f"Only values of compatible types can be compared."
                    )
    
    def _get_full_expression_type(self, expr: str, variable_types: Dict[str, str]) -> str:
        """Get the type of a full expression including Date/Period constructors."""
        expr = expr.strip()
        
        # Check for Date constructor
        if re.match(r'Date\s*\(', expr):
            return 'date'
        
        # Check for Period constructor
        if re.match(r'Period\s*\(', expr):
            return 'period'
        
        # Check for property access (e.g., k.year, Date(...).month)
        if re.search(r'\.(?:year|month|day)$', expr):
            return 'int'
        
        # Check for simple variable
        if expr in variable_types:
            return variable_types[expr]
        
        # Check for numeric literal
        if re.match(r'^-?\d+$', expr):
            return 'int'
        
        # Check for boolean literal
        if expr in ['True', 'False']:
            return 'bool'
        
        return None
    
    def _types_compatible(self, type1: str, type2: str) -> bool:
        """Check if two types are compatible for comparison."""
        return type1 == type2

    def generate_builder_code(
        self,
        constraints: List[Union[str, List[str]]],
    ) -> str:
        """
        Generate complete DateSMTBuilder code from structured constraint data.
        Supports CNF (Conjunctive Normal Form) format where constraints can be:
        - A string: single constraint (e.g., "x >= Date(2000,2,28)")
        - A list of strings: OR clause (e.g., ["x >= Date(2000,2,28)", "x <= Date(2000,2,29)"])
        
        All top-level constraints are ANDed together.
        
        Also supports variable declarations like "x: date", "y: int", "z: bool".
        All variables used in constraints must be explicitly declared.

        Args:
            constraints: List of constraint strings or lists of constraint strings (for OR clauses)

        Returns:
            Complete Python code string
            
        Raises:
            ValueError: If any variable used in constraints is not explicitly declared
        """
        code_lines = [
            "from z3 import Or, And, Not, Int, Bool, Implies",
            "from datesmt.enumeration_baseline import ConstraintWrapper",
            "builder = DateSMTBuilder()",
            "",
            "# Helper function for OR constraints that works with both Z3 and enumeration baseline",
            "def _or_constraints(*constraints):",
            "    # Check if we're using Z3 (BoolRef) or enumeration baseline (ConstraintWrapper)",
            "    from z3 import BoolRef",
            "    if any(isinstance(c, BoolRef) for c in constraints):",
            "        # Z3 mode: use Z3's Or",
            "        return Or(*constraints)",
            "    else:",
            "        # Enumeration baseline mode: create OR ConstraintWrapper",
            "        constraint_list = list(constraints)",
            "        return ConstraintWrapper(",
            "            lambda: any(c.evaluate() if hasattr(c, 'evaluate') else bool(c) for c in constraint_list),",
            "            or_constraints=constraint_list",
            "        )",
        ]

        # First, extract variable declarations
        variable_types = self.extract_variable_declarations(constraints)
        self.variable_types = variable_types
        
        # Filter out declarations from constraints
        filtered_constraints = self.filter_declarations_from_constraints(constraints)
        
        # Auto-extract variables from remaining constraints
        all_variables = self.extract_variables_from_constraints(filtered_constraints)
        
        # Infer types for undeclared variables from their usage context
        inferred_types = self.infer_variable_types_from_context(filtered_constraints)
        
        # Check for type conflicts between explicit declarations and inferred usage
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
                    f"'{var_name}' is declared as '{declared_type}' but used as '{inferred_type}' "
                    f"(inside Date() or Period() constructor)"
                )
            raise ValueError(
                f"Type conflict detected:\n  - " + "\n  - ".join(conflict_messages) + "\n"
                f"Variables used inside Date() or Period() constructors must be of type 'int', not 'date'."
            )
        
        # Merge inferred types into variable_types (explicit declarations take precedence)
        for var_name, var_type in inferred_types.items():
            if var_name not in variable_types:
                variable_types[var_name] = var_type
        
        # Check for undeclared variables that couldn't be inferred
        undeclared_vars = [var for var in all_variables if var not in variable_types]
        if undeclared_vars:
            # Check for common mistakes: lowercase boolean literals
            lowercase_bools = {'true': 'True', 'false': 'False'}
            bool_mistakes = [var for var in undeclared_vars if var in lowercase_bools]
            
            if bool_mistakes:
                corrections = [f"'{var}' should be '{lowercase_bools[var]}'" for var in bool_mistakes]
                raise ValueError(
                    f"Invalid boolean literal(s): {', '.join(corrections)}. "
                    f"Python uses capitalized 'True' and 'False' for boolean values."
                )
            
            undeclared_str = ", ".join(sorted(undeclared_vars))
            raise ValueError(
                f"Undeclared variables found in constraints: {undeclared_str}. "
                f"All variables must be explicitly declared using 'variable_name: type' syntax "
                f"(where type is 'date', 'int', or 'bool')."
            )
        
        # Check for type mismatches in comparisons (e.g., int == bool)
        self._check_comparison_type_mismatches(filtered_constraints, variable_types)
        
        # Add variable declarations
        for var_name, var_type in sorted(variable_types.items()):
            if var_type == 'date':
                code_lines.append(f'{var_name} = builder.add_date_var("{var_name}")')
            elif var_type == 'int':
                # Use builder.add_int_var() for int variables to ensure compatibility
                # with the implementation (bitvector or int mode)
                code_lines.append(f'{var_name} = builder.add_int_var("{var_name}")')
            elif var_type == 'bool':
                code_lines.append(f'{var_name} = builder.add_bool_var("{var_name}")')

        # Add constraints (using filtered constraints without declarations)
        for constraint_item in filtered_constraints:
            if isinstance(constraint_item, list):
                # OR clause: parse each constraint and combine with _or_constraints()
                if len(constraint_item) == 0:
                    continue
                elif len(constraint_item) == 1:
                    # Single constraint in list, treat as regular constraint
                    constraint_code = self.parse_constraint(constraint_item[0])
                    code_lines.append(constraint_code)
                else:
                    # Multiple constraints: combine with _or_constraints()
                    # We need to evaluate each constraint expression and pass the actual constraint objects
                    constraint_exprs = []
                    for constraint_str in constraint_item:
                        # Parse each constraint to get the expression
                        parsed = self.parse_constraint(constraint_str)
                        # Extract the constraint expression from "builder.add_constraint(...)"
                        # The parsed result is like "builder.add_constraint(x >= Date(2000,2,28))"
                        # We need to extract "x >= Date(2000,2,28)"
                        # Use a more robust approach: find the content between add_constraint( and the matching )
                        # Handle nested parentheses by counting them
                        start_idx = parsed.find('builder.add_constraint(')
                        if start_idx != -1:
                            start_idx += len('builder.add_constraint(')
                            # Find the matching closing paren, handling nested parentheses
                            paren_count = 0
                            i = start_idx
                            expr_end = -1
                            while i < len(parsed):
                                if parsed[i] == '(':
                                    paren_count += 1
                                elif parsed[i] == ')':
                                    if paren_count == 0:
                                        expr_end = i
                                        break
                                    paren_count -= 1
                                i += 1
                            
                            if expr_end != -1:
                                expr = parsed[start_idx:expr_end].strip()
                                constraint_exprs.append(expr)
                            else:
                                # Fallback: use the original constraint string
                                constraint_exprs.append(constraint_str)
                        else:
                            # Fallback: use the original constraint string
                            constraint_exprs.append(constraint_str)
                    
                    # Combine with _or_constraints() and add as single constraint
                    # Each constraint expression will be evaluated to get the actual constraint object
                    or_expr = "_or_constraints(" + ", ".join(constraint_exprs) + ")"
                    code_lines.append(f"builder.add_constraint({or_expr})")
            else:
                # Single constraint string
                constraint_code = self.parse_constraint(constraint_item)
                code_lines.append(constraint_code)

        # Add result assignment
        code_lines.append("result = builder")

        return "\n".join(code_lines)

    def parse_constraint_data(self, constraint_data: Dict[str, Any]) -> str:
        """
        Parse constraint data in the new format and return executable code.
        Supports CNF format where constraints can be strings or lists of strings.

        Args:
            constraint_data: Dictionary with 'constraints' field containing:
                - List of strings: ["x >= Date(2000,2,28)", "x <= Date(2000,3,1)"]
                - List of mixed: [["x >= Date(2000,2,28)", "x <= Date(2000,2,29)"], "x != Date(2000,3,1)"]
                The first format results in: (x >= Date(2000,2,28)) AND (x <= Date(2000,3,1))
                The second format results in: ((x >= Date(2000,2,28)) OR (x <= Date(2000,2,29))) AND (x != Date(2000,3,1))

        Returns:
            Executable Python code string
        """
        constraints = constraint_data.get('constraints', [])
        return self.generate_builder_code(constraints)
