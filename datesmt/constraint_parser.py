"""
Constraint parser for Date-SMT system using Lark parser generator.

This module provides functionality to parse constraints from the structured format
and convert them into executable DateSMTBuilder code using a context-free grammar.
"""

from typing import Any, Dict, List, Union
from lark import Lark, Transformer, Token
from .core import Date, Period
import re


class ConstraintTransformer(Transformer):
    """Transformer to convert Lark parse tree to Python code."""
    
    def constraint(self, items):
        """Transform a constraint into Python code."""
        if len(items) == 3:
            left, op, right = items
            return f"builder.add_constraint({left} {op} {right})"
        elif len(items) == 4:
            left, op, right, description = items
            return f"builder.add_constraint({left} {op} {right}, {description})"
        else:
            # Fallback for unexpected number of items
            return f"builder.add_constraint({' '.join(str(item) for item in items)})"
    
    def expression(self, items):
        """Handle expression precedence."""
        if len(items) == 1:
            return items[0]
        # This handles operator precedence automatically
        return " ".join(str(item) for item in items)
    
    def add(self, items):
        """Transform addition operation."""
        left, right = items
        return f"{left} + {right}"
    
    def sub(self, items):
        """Transform subtraction operation."""
        left, right = items
        return f"{left} - {right}"
    
    def mul(self, items):
        """Transform multiplication operation."""
        left, right = items
        return f"{left} * {right}"
    
    def term(self, items):
        """Handle term precedence."""
        if len(items) == 1:
            return items[0]
        return " ".join(str(item) for item in items)
    
    def factor(self, items):
        """Handle factor grouping."""
        if len(items) == 1:
            return items[0]
        return " ".join(str(item) for item in items)
    
    def parenthesized_expression(self, items):
        """Transform parenthesized expression."""
        if len(items) == 3:
            return f"({items[1]})"
        return " ".join(str(item) for item in items)
    
    def variable(self, items):
        """Transform variable reference."""
        return str(items[0])
    
    def concrete_date_constructor(self, items):
        """Transform concrete Date constructor (from grammar)."""
        year, month, day = items
        return f"Date({year}, {month}, {day})"
    
    def period_constructor(self, items):
        """Transform Period constructor."""
        years, months, days = items
        return f"Period({years}, {months}, {days})"
    
    def comparison_op(self, items):
        """Transform comparison operator."""
        if not items:
            return ""
        return str(items[0])
    
    def number(self, items):
        """Transform number literal."""
        return str(items[0])
    
    def string(self, items):
        """Transform string literal."""
        return str(items[0])
    
    def description(self, items):
        """Transform description string."""
        return str(items[0])


class ConstraintParser:
    """Parser for structured constraint format using Lark grammar."""

    def __init__(self):
        """Initialize the parser with Lark grammar."""
        self.date_vars: Dict[str, Any] = {}
        self.variable_types: Dict[str, str] = {}  # Maps variable name to type: 'date', 'int', or 'bool'
        
        # Define the grammar for constraint parsing
        self.grammar = """
            ?constraint: expression comparison_op expression [COMMA description]
            
            ?expression: term
                       | expression "+" term -> add
                       | expression "-" term -> sub
            
            ?term: factor
                 | term "*" factor -> mul
                 | term "/" factor -> div
            
            ?factor: variable
                   | concrete_date_constructor
                   | period_constructor
                   | number
                   | parenthesized_expression
            
            parenthesized_expression: LPAR expression RPAR
            
            LPAR: "("
            RPAR: ")"
            COMMA: ","
            
            variable: CNAME
            concrete_date_constructor: "Date" "(" number "," number "," number ")"
            period_constructor: "Period" "(" number "," number "," number ")"
            description: ESCAPED_STRING
            
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
            %import common.ESCAPED_STRING
            %ignore WS
        """
        
        # Create the Lark parser
        self.parser = Lark(
            self.grammar, 
            parser='lalr', 
            transformer=ConstraintTransformer(),
            start='constraint'
        )

    def parse_constraint(self, constraint_str: str) -> str:
        """
        Parse a single constraint string and return the corresponding Python code.

        Args:
            constraint_str: Constraint string like "x>=Date(2000,2,28)" or "x>=Date(2000,2,28), 'comment'"

        Returns:
            Python code string for the constraint
        """
        # Remove whitespace
        constraint_str = constraint_str.strip()

        # Check for invalid variable names that should raise ValueError
        if self._is_invalid_variable_name(constraint_str):
            raise ValueError(f"Could not parse constraint '{constraint_str}': Invalid variable name")

        try:
            # Parse using Lark
            result = self.parser.parse(constraint_str)
            return result
        except Exception as e:
            # For certain cases, be more permissive and pass through the text
            if self._should_pass_through(constraint_str, str(e)):
                return f"builder.add_constraint({constraint_str})"
            # Always raise ValueError for consistency with test expectations
            raise ValueError(f"Could not parse constraint '{constraint_str}': {e}")
    
    def _is_invalid_variable_name(self, constraint_str: str) -> bool:
        """Check if the constraint contains invalid variable names."""
        # Handle empty or whitespace-only strings
        if not constraint_str or constraint_str.isspace():
            return False
        
        # Check for invalid variable names like var-123, var.123, 123var
        # But exclude cases where hyphen/dot is followed by keywords like Period/Date or '('
        # This distinguishes "var-123" (invalid) from "z-Period(...)" (valid subtraction)
        pattern1 = r'\b[a-zA-Z_][a-zA-Z0-9_]*[-.][a-zA-Z0-9_]+\b'
        matches = re.finditer(pattern1, constraint_str)
        for match in matches:
            matched_text = match.group()
            # Check if the part after hyphen/dot is a keyword (Period, Date)
            parts = re.split(r'[-.]', matched_text, maxsplit=1)
            if len(parts) == 2:
                second_part = parts[1]
                # If it's a keyword, this is likely an operator, not an invalid variable name
                if second_part in ['Period', 'Date']:
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
    
    def _should_pass_through(self, constraint_str: str, error_msg: str) -> bool:
        """Check if the constraint should be passed through as text instead of raising an error."""
        # Handle empty or whitespace-only strings
        if not constraint_str or constraint_str.isspace():
            return False
        
        # For multiple operators, pass through
        if '>=' in constraint_str and constraint_str.count('>=') > 1:
            return True
        if '<=' in constraint_str and constraint_str.count('<=') > 1:
            return True
        if '==' in constraint_str and constraint_str.count('==') > 1:
            return True
        if '!=' in constraint_str and constraint_str.count('!=') > 1:
            return True
        if '>' in constraint_str and constraint_str.count('>') > 1:
            return True
        if '<' in constraint_str and constraint_str.count('<') > 1:
            return True
        
        # For incomplete constructors, pass through
        if 'Date(' in constraint_str and constraint_str.count(',') < 2:
            return True
        if 'Period(' in constraint_str and constraint_str.count(',') < 2:
            return True
        if 'Date(' in constraint_str and constraint_str.count(',') > 2:
            return True
        if 'Period(' in constraint_str and constraint_str.count(',') > 2:
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
        Extract all variable names from constraints (supports CNF format).
        
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
                # Check if this constraint is invalid (variable compared to period expression)
                if self._is_invalid_period_comparison(constraint):
                    print(f"Warning: Skipping invalid constraint '{constraint}' - period comparisons are not supported")
                    continue
                    
                # Find all potential variable names using regex
                # This matches CNAME pattern: [a-zA-Z_][a-zA-Z0-9_]*
                var_matches = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', constraint)
                
                for match in var_matches:
                    # Filter out keywords and constructors
                    if match not in ['Date', 'Period', 'and', 'or', 'not', 'True', 'False']:
                        variables.add(match)
        
        return sorted(list(variables))
    
    def _is_invalid_period_comparison(self, constraint: str) -> bool:
        """
        Check if a constraint compares a variable to a period expression.
        Such constraints are invalid because period variables are not supported.
        
        Args:
            constraint: Constraint string to check
            
        Returns:
            True if the constraint is invalid, False otherwise
        """
        # Check for invalid constraints that would result in Period or Bool types
        # Invalid cases (should NOT create date variables):
        # - Period ± Period = Period (e.g., z == Period(0, 1, 0) + Period(0, 1, 0))
        # - Period × Int = Period (e.g., z == Period(0, 1, 0) * 3)
        
        # Valid cases (SHOULD create date variables):
        # - Date ± Period = Date (e.g., y == x + Period(0, 1, 0), y2 == Period(0, 1, 1) + x)
        # - Date ▷◁ Date = Bool
        
        # Pattern 1: variable op Period(...) directly (invalid： Period = Period)
        direct_period_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*[=!<>]+\s*Period\([^)]*\)\s*$'
        if re.search(direct_period_pattern, constraint):
            return True
            
        # Pattern 2: variable op Period(...) + Period(...) (invalid: Period + Period = Period)
        period_plus_period_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*[=!<>]+\s*Period\([^)]*\)\s*\+\s*Period\('
        if re.search(period_plus_period_pattern, constraint):
            return True
            
        # Pattern 2b: variable op Period(...) - Period(...) (invalid: Period - Period = Period)
        period_minus_period_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*[=!<>]+\s*Period\([^)]*\)\s*-\s*Period\('
        if re.search(period_minus_period_pattern, constraint):
            return True
            
        # Pattern 3: variable op Period(...) * number (invalid: Period * Int = Period)
        period_multiply_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*[=!<>]+\s*Period\([^)]*\)\s*\*\s*\d+'
        if re.search(period_multiply_pattern, constraint):
            return True
            
        # Pattern 4: variable op number * Period(...) (invalid: Int * Period = Period)
        number_multiply_period_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\s*[=!<>]+\s*\d+\s*\*\s*Period\('
        if re.search(number_multiply_period_pattern, constraint):
            return True
            
        return False

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
            "from z3 import Or, Int, Bool",
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
        
        # Check for undeclared variables and raise error if found
        undeclared_vars = [var for var in all_variables if var not in variable_types]
        if undeclared_vars:
            undeclared_str = ", ".join(sorted(undeclared_vars))
            raise ValueError(
                f"Undeclared variables found in constraints: {undeclared_str}. "
                f"All variables must be explicitly declared using 'variable_name: type' syntax "
                f"(where type is 'date', 'int', or 'bool')."
            )
        
        # Add variable declarations
        for var_name, var_type in sorted(variable_types.items()):
            if var_type == 'date':
                code_lines.append(f'{var_name} = builder.add_date_var("{var_name}")')
            elif var_type == 'int':
                code_lines.append(f'{var_name} = Int("{var_name}")')
            elif var_type == 'bool':
                code_lines.append(f'{var_name} = Bool("{var_name}")')

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
                        # or "builder.add_constraint(x >= Date(2000,2,28), 'description')"
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
                                # Check if there's a description after (comma followed by string)
                                # Look for pattern: expr, 'description')
                                remaining = parsed[expr_end+1:].strip()
                                if remaining.startswith(','):
                                    # There's a description, but we already have the expr
                                    pass
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
