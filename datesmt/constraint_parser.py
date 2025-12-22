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
    
    def constraint(self, items) -> str:
        """Transform constraint (top level)."""
        return self.top_level_constraint(items)
    
    def top_level_constraint(self, items) -> str:
        """Transform a top-level constraint."""
        bool_expr = items[0]
        
        # Check if bool_expr already has builder.add_constraint wrapper (from implication)
        if bool_expr.startswith("builder.add_constraint("):
            return bool_expr
        
        return f"builder.add_constraint({bool_expr})"
    
    def implication(self, items) -> str:
        """Transform implication A -> B into Implies(A, B)."""
        # Earley parser might include the -> token, filter it out
        filtered = [item for item in items if str(item) != '->']
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
            return f"Implies({left}, {right})"
        # Fallback: use first two items
        left = str(items[0])
        right = str(items[-1])
        return f"Implies({left}, {right})"

    def or_op(self, items) -> str:
        """Transform OR operation A || B into Or(A, B)."""
        # Earley parser might include the operator token, filter it out
        filtered = [item for item in items if str(item) not in ('||', 'or', 'OR')]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
            return f"Or({left}, {right})"
        # Fallback: use first two items
        left = str(items[0])
        right = str(items[-1])
        return f"Or({left}, {right})"

    def and_op(self, items) -> str:
        """Transform AND operation A && B into And(A, B)."""
        # Earley parser might include the operator token, filter it out
        filtered = [item for item in items if str(item) not in ('&&', 'and', 'AND')]
        if len(filtered) == 2:
            left = str(filtered[0])
            right = str(filtered[1])
            return f"And({left}, {right})"
        # Fallback: use first two items
        left = str(items[0])
        right = str(items[-1])
        return f"And({left}, {right})"

    def not_op(self, items) -> str:
        """Transform NOT operation !A / not A into Not(A)."""
        # items = [NOT token, not_expr] or [not_expr] if NOT token is stripped
        filtered = [item for item in items if str(item) not in ('!', 'not', 'NOT')]
        if filtered:
            expr = str(filtered[0])
            return f"Not({expr})"
        expr = str(items[-1])
        return f"Not({expr})"
    
    def bool_atom(self, items) -> str:
        """Transform boolean atom (comparison, variable, bool literal, or parenthesized bool expr)."""
        # Handle parenthesized expressions: LPAR bool_expr RPAR
        # We don't need to preserve parens since Z3 function calls handle precedence
        if len(items) == 3 and str(items[0]) == '(' and str(items[2]) == ')':
            return str(items[1])
        return items[0]
    
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
        # Earley parser might include the + token, filter it out
        filtered = [item for item in items if str(item) != '+']
        if len(filtered) == 2:
            return f"{filtered[0]} + {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} + {items[-1]}"
    
    def sub(self, items) -> str:
        """Transform subtraction operation."""
        # Earley parser might include the - token, filter it out
        filtered = [item for item in items if str(item) != '-']
        if len(filtered) == 2:
            return f"{filtered[0]} - {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} - {items[-1]}"
    
    def mul(self, items) -> str:
        """Transform multiplication operation."""
        # Earley parser might include the * token, filter it out
        filtered = [item for item in items if str(item) != '*']
        if len(filtered) == 2:
            return f"{filtered[0]} * {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} * {items[-1]}"
    
    def floordiv(self, items) -> str:
        """Transform integer division operation."""
        # Earley parser might include the / token, filter it out
        filtered = [item for item in items if str(item) != '/']
        if len(filtered) == 2:
            return f"{filtered[0]} / {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} / {items[-1]}"
    
    def mod(self, items) -> str:
        """Transform modulo operation."""
        # Earley parser might include the % token, filter it out
        filtered = [item for item in items if str(item) != '%']
        if len(filtered) == 2:
            return f"{filtered[0]} % {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} % {items[-1]}"
    
    def pow(self, items) -> str:
        """Transform exponentiation operation."""
        # Earley parser might include the ** token, filter it out
        filtered = [item for item in items if str(item) != '**']
        if len(filtered) == 2:
            return f"{filtered[0]} ** {filtered[1]}"
        # Fallback: use first two items
        return f"{items[0]} ** {items[-1]}"
    
    def term(self, items) -> str:
        """Handle term precedence."""
        if len(items) == 1:
            return items[0]
        return " ".join(str(item) for item in items)
    
    def factor(self, items) -> str:
        """Handle factor grouping."""
        if len(items) == 1:
            return items[0]
        # Handle parenthesized expressions: LPAR expr RPAR or LPAR comparison_expr RPAR
        # Lark passes [LPAR_token, transformed_expr, RPAR_token], so we wrap the middle item
        if len(items) == 3:
            return f"({items[1]})"
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
        # items = [variable, DOT, property_name] - DOT is ignored
        var_name = items[0]
        property_name = items[2]
        return f"{var_name}.{property_name}"
    
    def date_property_access(self, items) -> str:
        """Transform property access on Date constructor like Date(1991,2,3).month."""
        # items = [date_constructor, DOT, property_name] - DOT is ignored
        date_expr = items[0]
        property_name = items[2]
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
        
        # Define the grammar for constraint parsing (LALR, precedence: NOT > AND > OR > IMPLIES)
        self.grammar = r"""
            constraint: top_level_constraint

            top_level_constraint: bool_expr

            ?bool_expr: implication

            ?implication: or_expr IMPLIES bool_expr -> implication
                        | or_expr

            ?or_expr: and_expr OR or_expr -> or_op
                    | and_expr

            ?and_expr: not_expr AND and_expr -> and_op
                     | not_expr

            ?not_expr: NOT not_expr -> not_op
                     | bool_atom

            ?bool_atom: comparison_expr
                      | variable
                      | not_expr
                      | LPAR bool_expr RPAR

            comparison_expr: expression comparison_op expression
                          | bool_atom comparison_op bool_atom

            IMPLIES: "->"
            OR: "||" | /\bor\b/i | /\bOR\b/
            AND: "&&" | /\band\b/i | /\bAND\b/
            NOT: "!" | /\bnot\b/i | /\bNOT\b/
            PLUS: "+"
            MINUS: "-"
            STAR: "*"
            DIV:  "/"
            MOD: "%"
            POW: "**"
            LPAR: "("
            RPAR: ")"
            DOT: "."

            ?expression: term
                       | expression PLUS term   -> add
                       | expression MINUS term  -> sub

            ?term: power
                 | term STAR power -> mul
                 | term DIV power  -> floordiv
                 | term MOD power  -> mod
            
            ?power: factor
                  | factor POW power -> pow

            ?factor: variable
                   | date_constructor
                   | period_constructor
                   | number
                   | property_access
                   | date_property_access
                   | bool_literal
                   | LPAR expression RPAR
                   | LPAR comparison_expr RPAR

            property_access: variable DOT property_name
            date_property_access: date_constructor DOT property_name

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

        # Create the Lark parser with Earley algorithm (handles ambiguities better)
        self.parser = Lark(
            self.grammar,
            parser="earley",
            start="constraint",
        )
        self.transformer = ConstraintTransformer()

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
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth < 0:
                    # More closing than opening parens at this position
                    context_start = max(0, i - 20)
                    context_end = min(len(constraint_str), i + 20)
                    context = constraint_str[context_start:context_end]
                    pointer = ' ' * (i - context_start) + '^'
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
                if char == '(':
                    if temp_depth == 0:
                        first_unmatched = i
                    temp_depth += 1
                elif char == ')':
                    temp_depth -= 1
                    if temp_depth == 0:
                        first_unmatched = -1
            
            context_start = max(0, first_unmatched - 20)
            context_end = min(len(constraint_str), first_unmatched + 40)
            context = constraint_str[context_start:context_end]
            pointer = ' ' * (first_unmatched - context_start) + '^'
            raise ValueError(
                f"Unbalanced parentheses: {depth} unclosed opening '(' found, starting at position {first_unmatched}\n"
                f"  {context}\n"
                f"  {pointer}"
            )

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

        # Check for unbalanced parentheses
        self._validate_parentheses_balance(constraint_str)

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
        declaration_pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$'
        
        for constraint in constraints:
            constraint = constraint.strip()
            match = re.match(declaration_pattern, constraint, re.IGNORECASE)
            if match:
                var_name = match.group(1)
                var_type = match.group(2).lower()  # Normalize to lowercase
                if var_type in ['date', 'int', 'bool']:
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
        declaration_pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(date|int|bool)\s*$'
        
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
            cleaned_constraint = re.sub(r'\.(?:year|month|day)\b', '', constraint)
                
            # Find all potential variable names using regex
            # This matches CNAME pattern: [a-zA-Z_][a-zA-Z0-9_]*
            var_matches = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', cleaned_constraint)
            
            for match in var_matches:
                # Filter out keywords and constructors
                if match not in ['Date', 'Period', 'And', 'Or', 'Not', 'Implies', 'and', 'or', 'not', 'True', 'False']:
                    variables.add(match)
        
        return sorted(list(variables))
    
    def infer_variable_types_from_context(self, constraints: List[str]) -> Dict[str, str]:
        """
        Infer variable types from their usage context in constraints.
        
        Variables used inside Date() or Period() constructors are inferred as 'int'.
        For all other cases, users must explicitly declare variable types.
        
        Args:
            constraints: List of constraint strings
            
        Returns:
            Dictionary mapping inferred variable names to their types
        """
        inferred_types = {}
        
        for constraint in constraints:
            # Find variables inside Date() constructor arguments
            # Pattern: Date(arg1, arg2, arg3) where args can be expressions with variables
            date_pattern = r'Date\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)'
            date_matches = re.finditer(date_pattern, constraint)
            for match in date_matches:
                for arg in [match.group(1), match.group(2), match.group(3)]:
                    # Extract variable names from each argument
                    # But exclude variables that are part of property access (e.g., taxable_year_end.year)
                    # We only want variables used directly, not via property access
                    var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', arg)
                    for var_name in var_names:
                        if var_name not in ['Date', 'Period', 'And', 'Or', 'Not', 'Implies', 'and', 'or', 'not', 'True', 'False', 'year', 'month', 'day']:
                            # Check if this variable appears as part of a property access pattern
                            # e.g., if arg contains "taxable_year_end.year", we should NOT infer taxable_year_end as int
                            property_access_pattern = rf'\b{re.escape(var_name)}\s*\.\s*(?:year|month|day)\b'
                            if not re.search(property_access_pattern, arg):
                                inferred_types[var_name] = 'int'
    
        
        return inferred_types
    
    def infer_date_component_bounds(self, constraints: List[str]) -> Dict[str, str]:
        """
        Infer which Date() component position each integer variable is used in.
        
        This allows us to automatically add appropriate bounds constraints:
        - Position 1 (year): 1900 <= var <= 2100
        - Position 2 (month): 1 <= var <= 12
        - Position 3 (day): 1 <= var <= 31
        
        Args:
            constraints: List of constraint strings
            
        Returns:
            Dictionary mapping variable names to their component type ('year', 'month', 'day', or 'mixed')
            'mixed' means the variable is used in multiple positions
        """
        component_usage = {}  # var_name -> set of component types
        
        for constraint in constraints:
            # Find Date() constructors and their arguments
            date_pattern = r'Date\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^,)]+)\s*\)'
            date_matches = re.finditer(date_pattern, constraint)
            
            for match in date_matches:
                args = [match.group(1), match.group(2), match.group(3)]
                component_types = ['year', 'month', 'day']
                
                for arg, component_type in zip(args, component_types):
                    # Extract variable names from this argument
                    var_names = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', arg)
                    for var_name in var_names:
                        if var_name not in ['Date', 'Period', 'And', 'Or', 'Not', 'Implies', 'and', 'or', 'not', 'True', 'False', 'year', 'month', 'day']:
                            # Check if this is a property access (should skip)
                            property_access_pattern = rf'\b{re.escape(var_name)}\s*\.\s*(?:year|month|day)\b'
                            if not re.search(property_access_pattern, arg):
                                # This variable is used in this component position
                                if var_name not in component_usage:
                                    component_usage[var_name] = set()
                                component_usage[var_name].add(component_type)
        
        # Convert sets to single strings, or 'mixed' if used in multiple positions
        result = {}
        for var_name, components in component_usage.items():
            if len(components) == 1:
                result[var_name] = list(components)[0]
            else:
                result[var_name] = 'mixed'
        
        return result

    # ========================================================================
    # TYPE CHECKING METHODS (CURRENTLY DISABLED)
    # ========================================================================
    # These methods were used to enforce strict type checking at parse time,
    # rejecting comparisons like Bool == Int even though Z3 allows them.
    # Currently disabled to allow Z3's more permissive runtime type handling.
    # ========================================================================
    
    def _check_comparison_type_mismatches(
        self, 
        constraints: List[str], 
        variable_types: Dict[str, str]
    ) -> None:
        """
        [DISABLED] Check for type mismatches in comparisons between variables.
        
        For example, comparing an int variable with a bool variable is invalid.
        """
        for constraint in constraints:
            self._check_constraint_comparisons(constraint, variable_types)
    
    def _check_constraint_comparisons(
        self,
        constraint: str,
        variable_types: Dict[str, str]
    ) -> None:
        """
        [DISABLED] Recursively check comparisons in a constraint, handling logical operators.
        """
        constraint = constraint.strip()
        
        # Handle implication: A -> B
        # Split by '->' and check both sides
        if '->' in constraint:
            # Find '->' outside of parentheses
            parts = self._split_by_operator(constraint, '->')
            if len(parts) == 2:
                # Check both sides of implication
                self._check_constraint_comparisons(parts[0], variable_types)
                self._check_constraint_comparisons(parts[1], variable_types)
                return
        
        # Handle logical OR: A || B
        or_parts = self._split_by_operator(constraint, '||')
        if len(or_parts) > 1:
            # Check each part separately
            for part in or_parts:
                self._check_constraint_comparisons(part, variable_types)
            return
        
        # Handle logical AND: A && B
        and_parts = self._split_by_operator(constraint, '&&')
        if len(and_parts) > 1:
            # Check each part separately
            for part in and_parts:
                self._check_constraint_comparisons(part, variable_types)
            return
        
        # Remove outer parentheses if present
        if constraint.startswith('(') and constraint.endswith(')'):
            # Check if these are matching outer parentheses
            depth = 0
            for i, c in enumerate(constraint):
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                if depth == 0 and i < len(constraint) - 1:
                    break
            if depth == 0 and i == len(constraint) - 1:
                # Outer parentheses match, remove them
                self._check_constraint_comparisons(constraint[1:-1], variable_types)
                return
        
        # Now check for comparison operators
        comp_match = re.search(r'(==|!=|>=|<=|>|<)', constraint)
        if not comp_match:
            return
        
        op = comp_match.group(1)
        left_expr = constraint[:comp_match.start()].strip()
        right_expr = constraint[comp_match.end():].strip()
        
        # Get types for both sides
        left_type = self._get_full_expression_type(left_expr, variable_types)
        right_type = self._get_full_expression_type(right_expr, variable_types)
        
        if left_type is None or right_type is None:
            return
        
        if not self._types_compatible(left_type, right_type):
            raise ValueError(
                f"Type mismatch in constraint '{constraint}': "
                f"cannot compare '{left_expr}' (type: {left_type}) with "
                f"'{right_expr}' (type: {right_type}). "
                f"Only values of compatible types can be compared."
            )
    
    def _split_by_operator(self, expr: str, op: str) -> List[str]:
        """
        [DISABLED - used by type checking] Split expression by operator, respecting parentheses.
        Returns list with single element if operator not found at depth 0.
        """
        parts = []
        current = []
        depth = 0
        i = 0
        
        while i < len(expr):
            if expr[i] == '(':
                depth += 1
                current.append(expr[i])
                i += 1
            elif expr[i] == ')':
                depth -= 1
                current.append(expr[i])
                i += 1
            elif depth == 0 and expr[i:i+len(op)] == op:
                # Found operator at depth 0
                parts.append(''.join(current).strip())
                current = []
                i += len(op)
            else:
                current.append(expr[i])
                i += 1
        
        # Add the last part
        if current:
            parts.append(''.join(current).strip())
        
        return parts if len(parts) > 1 else [expr]
    
    def _get_full_expression_type(self, expr: str, variable_types: Dict[str, str]) -> str:
        """[DISABLED - used by type checking] Get the type of a full expression including Date/Period constructors."""
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
        """[DISABLED - used by type checking] Check if two types are compatible for comparison."""
        return type1 == type2

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
            filtered_constraints = constraints  # No need to filter, constraints don't contain declarations
        else:
            # Old format: declarations mixed with constraints (backward compatibility)
            variable_types = self.extract_variable_declarations(constraints)
            filtered_constraints = self.filter_declarations_from_constraints(constraints)
        
        self.variable_types = variable_types

        # Validate parentheses balance in all constraints FIRST (before any other validation)
        for constraint in filtered_constraints:
            self._validate_parentheses_balance(constraint)

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
        # NOTE: Type checking disabled - Z3 handles type conversions at runtime
        # self._check_comparison_type_mismatches(filtered_constraints, variable_types)
        
        # Infer bounds for integer variables used in Date() constructors
        component_bounds = self.infer_date_component_bounds(filtered_constraints)
        
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
        
        # Add natural bounds constraints for integer variables used in Date() constructors
        code_lines.append("")
        code_lines.append("# Automatic bounds for Date() component variables")
        for var_name, component_type in sorted(component_bounds.items()):
            if component_type == 'year':
                code_lines.append(f'builder.add_constraint({var_name} >= 1900)')
                code_lines.append(f'builder.add_constraint({var_name} <= 2100)')
            elif component_type == 'month':
                code_lines.append(f'builder.add_constraint({var_name} >= 1)')
                code_lines.append(f'builder.add_constraint({var_name} <= 12)')
            elif component_type == 'day':
                code_lines.append(f'builder.add_constraint({var_name} >= 1)')
                code_lines.append(f'builder.add_constraint({var_name} <= 31)')
            elif component_type == 'mixed':
                # Variable used in multiple positions - use most restrictive bounds
                code_lines.append(f'# Warning: {var_name} used in multiple Date() positions - using conservative bounds')
                code_lines.append(f'builder.add_constraint({var_name} >= 1)')
                code_lines.append(f'builder.add_constraint({var_name} <= 2100)')

        # Add constraints (using filtered constraints without declarations)
        # Each constraint is a full boolean expression - parse and add directly
        code_lines.append("")
        for constraint_str in filtered_constraints:
            constraint_code = self.parse_constraint(constraint_str)
            code_lines.append(constraint_code)

        # Add result assignment
        code_lines.append("result = builder")

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
        constraints = constraint_data.get('constraints', [])
        declarations = constraint_data.get('declarations', None)
        
        # Ensure constraints is a list of strings (no nested lists)
        for constraint in constraints:
            if isinstance(constraint, list):
                raise ValueError("Nested lists are not supported. Each constraint must be a string with boolean operators.")
        
        # If declarations provided, ensure it's also a list of strings
        if declarations is not None:
            for declaration in declarations:
                if isinstance(declaration, list):
                    raise ValueError("Nested lists are not supported. Each declaration must be a string like 'x: date'.")
                if not isinstance(declaration, str):
                    raise ValueError(f"Invalid declaration format: {declaration}. Expected string like 'x: date'.")
        
        return self.generate_builder_code(constraints, declarations)
