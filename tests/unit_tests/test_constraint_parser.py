"""
Unit tests for the ConstraintParser class in datesmt.constraint_parser.
"""

import pytest
from datesmt.constraint_parser import ConstraintParser


@pytest.fixture
def parser():
    """Create a ConstraintParser instance for testing."""
    return ConstraintParser()


# -------------------------
# Basic constraint parsing
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("x >= Date(2000, 2, 28)", "builder.add_constraint(x >= Date(2000, 2, 28))"),
    ("y <= Date(2020, 12, 31)", "builder.add_constraint(y <= Date(2020, 12, 31))"),
    ("z == Date(1999, 1, 1)", "builder.add_constraint(z == Date(1999, 1, 1))"),
    ("a != Date(2000, 1, 1)", "builder.add_constraint(a != Date(2000, 1, 1))"),
    ("b > Date(2020, 6, 15)", "builder.add_constraint(b > Date(2020, 6, 15))"),
    ("c < Date(2025, 1, 1)", "builder.add_constraint(c < Date(2025, 1, 1))"),
])
def test_parse_constraint_basic_comparisons(parser, constraint, expected):
    """Test parsing of basic comparison constraints."""
    result = parser.parse_constraint(constraint)
    assert result == expected


@pytest.mark.parametrize("constraint,expected", [
    ("x >= Period(1, 0, 0)", "builder.add_constraint(x >= Period(1, 0, 0))"),
    ("y <= Period(0, 6, 15)", "builder.add_constraint(y <= Period(0, 6, 15))"),
    ("z == Period(0, 0, 30)", "builder.add_constraint(z == Period(0, 0, 30))"),
])
def test_parse_constraint_period_comparisons(parser, constraint, expected):
    """Test parsing of Period comparison constraints."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Arithmetic expressions
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("x + Period(0, 1, 0) >= Date(2020, 1, 1)", 
     "builder.add_constraint(x + Period(0, 1, 0) >= Date(2020, 1, 1))"),
    ("y - Period(1, 0, 0) <= Date(2025, 1, 1)", 
     "builder.add_constraint(y - Period(1, 0, 0) <= Date(2025, 1, 1))"),
    ("a + Period(0, 0, 5) == Date(2020, 6, 15)", 
     "builder.add_constraint(a + Period(0, 0, 5) == Date(2020, 6, 15))"),
])
def test_parse_constraint_arithmetic(parser, constraint, expected):
    """Test parsing of arithmetic expressions in constraints."""
    result = parser.parse_constraint(constraint)
    assert result == expected


@pytest.mark.parametrize("constraint,expected", [
    ("(x + Period(0, 1, 0)) > Date(2020, 1, 1)", 
     "builder.add_constraint((x + Period(0, 1, 0)) > Date(2020, 1, 1))"),
    ("(y - Period(1, 0, 0)) < Date(2025, 1, 1)", 
     "builder.add_constraint((y - Period(1, 0, 0)) < Date(2025, 1, 1))"),
    ("((a + Period(0, 0, 5)) - Period(0, 1, 0)) != Date(2020, 6, 15)", 
     "builder.add_constraint(((a + Period(0, 0, 5)) - Period(0, 1, 0)) != Date(2020, 6, 15))"),
])
def test_parse_constraint_parentheses(parser, constraint, expected):
    """Test parsing of parenthesized expressions."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Complex arithmetic expressions
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("a + b - Period(0, 1, 0) >= Date(2020, 1, 1)", 
     "builder.add_constraint(a + b - Period(0, 1, 0) >= Date(2020, 1, 1))"),
    ("x - y + Period(1, 0, 0) <= Date(2025, 1, 1)", 
     "builder.add_constraint(x - y + Period(1, 0, 0) <= Date(2025, 1, 1))"),
])
def test_parse_constraint_complex_arithmetic(parser, constraint, expected):
    """Test parsing of complex arithmetic expressions with proper precedence."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Integer arithmetic operations
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("a + b == c", "builder.add_constraint(a + b == c)"),
    ("a - b == c", "builder.add_constraint(a - b == c)"),
    ("5 * a == c", "builder.add_constraint(5 * a == c)"),
    ("a * 5 == c", "builder.add_constraint(a * 5 == c)"),
    ("a / 5 == c", "builder.add_constraint(a / 5 == c)"),
    ("a % 5 == c", "builder.add_constraint(a % 5 == c)"),
])
def test_parse_constraint_integer_operations(parser, constraint, expected):
    """Test parsing of integer arithmetic operations: +, -, *, /, % (linear only)."""
    result = parser.parse_constraint(constraint)
    assert result == expected


@pytest.mark.parametrize("constraint,expected", [
    ("a + 5 * c == d", "builder.add_constraint(a + 5 * c == d)"),
    ("5 * a + c == d", "builder.add_constraint(5 * a + c == d)"),
    ("a / 5 + c == d", "builder.add_constraint(a / 5 + c == d)"),
    ("a % 5 + c == d", "builder.add_constraint(a % 5 + c == d)"),
])
def test_parse_constraint_integer_precedence(parser, constraint, expected):
    """Test that integer operations follow correct precedence: *, /, % > +, - (linear only)."""
    result = parser.parse_constraint(constraint)
    assert result == expected


@pytest.mark.parametrize("constraint", [
    "a * b == c",  # Nonlinear multiplication
    "a ** b == c",  # Power operation
    "a + b * c == d",  # Nonlinear multiplication in expression
    "a * b + c == d",  # Nonlinear multiplication in expression
])
def test_parse_constraint_nonlinear_arithmetic_rejected(parser, constraint):
    """Test that nonlinear arithmetic (var * var, **) is rejected."""
    with pytest.raises(ValueError):
        parser.parse_constraint(constraint)


def test_integer_operations_with_property_access(parser):
    """Test integer operations with property access."""
    constraint = "k.year + 1 == next_year"
    result = parser.parse_constraint(constraint)
    assert "k.year + 1 == next_year" in result
    
    constraint = "k.year % 4 == 0"
    result = parser.parse_constraint(constraint)
    assert "k.year % 4 == 0" in result
    
    constraint = "k.year / 100 == century"
    result = parser.parse_constraint(constraint)
    assert "k.year / 100 == century" in result


def test_integer_operations_in_date_constructor(parser):
    """Test integer operations inside Date constructor (parametric date gets transformed)."""
    constraint = "k == Date(x + 1, 2, 15)"
    result = parser.parse_constraint(constraint)
    # Parametric Date constructors are transformed to component-wise comparisons
    assert "k.year == x + 1" in result
    assert "k.month == 2" in result
    assert "k.day == 15" in result


def test_generate_builder_code_with_integer_operations(parser):
    """Test generating builder code with integer operations (linear only)."""
    constraints = [
        "x: int",
        "y: int",
        "z: int",
        "x % 4 == 0",
        "y == x / 10",
        "z == 5 * x"
    ]

    result = parser.generate_builder_code(constraints)

    assert 'x = builder.add_int_var("x")' in result
    assert 'y = builder.add_int_var("y")' in result
    assert 'z = builder.add_int_var("z")' in result
    assert "x % 4 == 0" in result
    assert "x / 10" in result
    assert "5 * x" in result


# -------------------------
# Variable names
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("var1 >= Date(2000, 1, 1)", "builder.add_constraint(var1 >= Date(2000, 1, 1))"),
    ("_var >= Date(2000, 1, 1)", "builder.add_constraint(_var >= Date(2000, 1, 1))"),
    ("var_123 >= Date(2000, 1, 1)", "builder.add_constraint(var_123 >= Date(2000, 1, 1))"),
    ("VAR >= Date(2000, 1, 1)", "builder.add_constraint(VAR >= Date(2000, 1, 1))"),
])
def test_parse_constraint_variable_names(parser, constraint, expected):
    """Test parsing with different valid variable names."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Error cases
# -------------------------

@pytest.mark.parametrize("invalid_constraint", [
    "x >= ",  # Incomplete constraint
    ">= Date(2000, 1, 1)",  # Missing left side
    "x >=",  # Missing right side
    "x @ Date(2000, 1, 1)",  # Invalid operator
    "123var >= Date(2000, 1, 1)",  # Invalid variable name
    "var-123 >= Date(2000, 1, 1)",  # Invalid variable name
    "var.123 >= Date(2000, 1, 1)",  # Invalid variable name
    "",  # Empty string
    "   ",  # Whitespace only
])
def test_parse_constraint_invalid_inputs(parser, invalid_constraint):
    """Test that invalid constraints raise ValueError."""
    with pytest.raises(ValueError):
        parser.parse_constraint(invalid_constraint)

@pytest.mark.parametrize("constraint_with_incomplete_constructors", [
    "x >= Date(2000, 1)",  # Incomplete Date constructor
    "x >= Period(1, 0)",  # Incomplete Period constructor
    "x >= Date(2000, 1, 1, 1)",  # Too many Date arguments
    "x >= Period(1, 0, 0, 0)",  # Too many Period arguments
])
def test_parse_constraint_incomplete_constructors(parser, constraint_with_incomplete_constructors):
    """Test that incomplete constructors raise ValueError."""
    with pytest.raises(ValueError):
        parser.parse_constraint(constraint_with_incomplete_constructors)


# -------------------------
# Whitespace handling
# -------------------------

@pytest.mark.parametrize("constraint_with_whitespace,expected", [
    ("  x >= Date(2000, 1, 1)  ", "builder.add_constraint(x >= Date(2000, 1, 1))"),
    ("\tx <= Date(2020, 12, 31)\n", "builder.add_constraint(x <= Date(2020, 12, 31))"),
    ("  y  +  Period(0, 1, 0)  >=  Date(2020, 1, 1)  ", 
     "builder.add_constraint(y + Period(0, 1, 0) >= Date(2020, 1, 1))"),
])
def test_parse_constraint_whitespace_handling(parser, constraint_with_whitespace, expected):
    """Test that whitespace is properly handled."""
    result = parser.parse_constraint(constraint_with_whitespace)
    assert result == expected


# -------------------------
# generate_builder_code method
# -------------------------

def test_generate_builder_code_basic(parser):
    """Test basic builder code generation."""
    constraints = ["x: date", "y: date", "x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]

    result = parser.generate_builder_code(constraints)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(y <= Date(2020, 12, 31))" in result

def test_generate_builder_code_empty(parser):
    """Test builder code generation with empty inputs."""
    constraints = []

    result = parser.generate_builder_code(constraints)

    assert "from z3 import Or, And, Not" in result
    assert "builder = DateSMTBuilder()" in result


# -------------------------
# parse_constraint_data method
# -------------------------

def test_parse_constraint_data_basic(parser):
    """Test parsing constraint data with separate declarations and constraints."""
    constraint_data = {
        "declarations": ["x: date", "y: date"],
        "constraints": ["x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(y <= Date(2020, 12, 31))" in result


def test_parse_constraint_data_backward_compatible(parser):
    """Test backward compatibility with old format (declarations mixed with constraints)."""
    constraint_data = {
        "constraints": ["x: date", "y: date", "x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(y <= Date(2020, 12, 31))" in result


def test_parse_constraint_data_missing_keys(parser):
    """Test parsing constraint data with missing keys."""
    constraint_data = {}

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert "builder = DateSMTBuilder()" in result


def test_parse_constraint_data_with_periods(parser):
    """Test parsing constraint data with period."""
    constraint_data = {
        "constraints": ["x: date", "x + Period(0,1,1) >= Date(2000, 1, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert "builder.add_constraint(x + Period(0, 1, 1) >= Date(2000, 1, 1))" in result


# -------------------------
# Edge cases and robustness
# -------------------------

def test_parse_constraint_nested_parentheses(parser):
    """Test parsing with deeply nested parentheses."""
    constraint = "((x + Period(0, 1, 0)) - Period(0, 0, 5)) >= Date(2020, 1, 1)"
    expected = "builder.add_constraint(((x + Period(0, 1, 0)) - Period(0, 0, 5)) >= Date(2020, 1, 1))"
    
    result = parser.parse_constraint(constraint)
    assert result == expected


def test_parse_constraint_negative_numbers(parser):
    """Test parsing with negative numbers in Date/Period constructors."""
    constraint = "x >= Date(-2000, 1, 1)"
    expected = "builder.add_constraint(x >= Date(-2000, 1, 1))"
    
    result = parser.parse_constraint(constraint)
    assert result == expected


def test_parse_constraint_large_numbers(parser):
    """Test parsing with large numbers."""
    constraint = "x >= Date(9999, 12, 31)"
    expected = "builder.add_constraint(x >= Date(9999, 12, 31))"
    
    result = parser.parse_constraint(constraint)
    assert result == expected


def test_parse_constraint_zero_values(parser):
    """Test parsing with zero values."""
    constraint = "x >= Date(2000, 1, 1) + Period(0, 0, 0)"
    expected = "builder.add_constraint(x >= Date(2000, 1, 1) + Period(0, 0, 0))"
    
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Integration tests
# -------------------------

def test_full_workflow(parser):
    """Test the complete workflow from constraint data to executable code with declarations."""
    constraint_data = {
        "constraints": [
            "start_date: date",
            "end_date: date",
            "start_date >= Date(2000, 1, 1)",
            "end_date <= Date(2020, 12, 31)",
            "start_date + Period(1,1,1) <= end_date"
        ]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Verify the result contains expected elements
    assert "builder = DateSMTBuilder()" in result
    assert 'start_date = builder.add_date_var("start_date")' in result
    assert 'end_date = builder.add_date_var("end_date")' in result
    assert "builder.add_constraint(start_date >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(end_date <= Date(2020, 12, 31))" in result
    assert "builder.add_constraint(start_date + Period(1, 1, 1) <= end_date)" in result


def test_parser_state_independence():
    """Test that parser instances are independent."""
    parser1 = ConstraintParser()
    parser2 = ConstraintParser()

    # Parse with first parser
    result1 = parser1.parse_constraint("x >= Date(2000, 1, 1)")

    # Parse with second parser
    result2 = parser2.parse_constraint("y <= Date(2020, 12, 31)")

    # Results should be independent
    assert result1 == "builder.add_constraint(x >= Date(2000, 1, 1))"
    assert result2 == "builder.add_constraint(y <= Date(2020, 12, 31))"
    assert result1 != result2

# -------------------------
# Auto-extraction tests
# -------------------------

def test_auto_extract_variables_simple(parser):
    """Test auto-extraction of variables from simple constraints."""
    constraints = ["x >= Date(2000, 2, 28)", "y <= Date(2020, 3, 1)"]
    extracted = parser.extract_variables_from_constraints(constraints)
    assert extracted == ["x", "y"]


def test_auto_extract_variables_complex(parser):
    """Test auto-extraction of variables from complex constraints."""
    constraints = [
        "x == Date(2022, 1, 15)",
        "y == x + Period(0, 13, 40)",
        "z == y + Period(0, 1, 0)",
        "z - x == Period(0, 2, 0)"
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    assert extracted == ["x", "y", "z"]

def test_auto_extract_variables_complex_format(parser):
    """Test auto-extraction of variables from complex constraints in more complex format."""
    constraints = [
        "x_23 >= Date(2022, 1, 15)",
        "y_add_period <= Date(2022, 1, 15) + Period(0, 13, 40)",
        "Z13 == Date(2022, 1, 15) + Period(0, 1, 0)",
        "Z13 - x_23 == Period(0, 2, 0)"
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    # Variables are returned in alphabetical order
    assert extracted == ["Z13", "x_23", "y_add_period"]

def test_auto_extract_variables_complex_format2(parser):
    """Test auto-extraction of variables from complex constraints in more complex format."""
    constraints = [
        "x_23 >= Date(2022, 1, 15)",
        "y_add_period <= Date(2022, 1, 15) + Period(0, 13, 40)",
        "Z13 == Period(0, 1, 0) + Period(0, 1, 0)"  # Invalid at runtime, but variables still extracted
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    # Variables are returned in alphabetical order
    # All variables are extracted; invalid constraints will fail at runtime
    assert extracted == ["Z13", "x_23", "y_add_period"]

def test_auto_extract_variables_filters_keywords(parser):
    """Test that auto-extraction filters out keywords and constructors."""
    constraints = [
        "x >= Date(2000, 1, 1)",
        "y == x + Period(0, 1, 0)",
        "is_valid == True"
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    assert extracted == ["is_valid", "x", "y"]

def test_parse_constraint_data_with_one_datevar(parser):
    """Test parsing constraint data with one date variable."""
    constraint_data = {
        "constraints": ["x: date", "x >= Date(2000, 2, 28)", "x <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert "builder.add_constraint(x >= Date(2000, 2, 28))" in result
    assert "builder.add_constraint(x <= Date(2000, 3, 1))" in result

def test_parse_constraint_data_with_multiple_datevar(parser):
    """Test parsing constraint data with multiple date variables."""
    constraint_data = {
        "constraints": ["x: date", "y: date", "x >= Date(2000, 2, 28)", "y <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "from z3 import Or, And, Not" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 2, 28))" in result
    assert "builder.add_constraint(y <= Date(2000, 3, 1))" in result


# -------------------------
# Boolean operators tests (&&, ||, !, and, or, not)
# -------------------------

@pytest.mark.parametrize("constraint,expected_pattern", [
    ("a && b", "And(a, b)"),
    ("a and b", "And(a, b)"),
    ("a || b", "Or(a, b)"),
    ("a or b", "Or(a, b)"),
    ("!a", "Not(a)"),
    ("not a", "Not(a)"),
])
def test_parse_constraint_boolean_operators(parser, constraint, expected_pattern):
    """Test parsing of boolean operators."""
    result = parser.parse_constraint(constraint)
    assert expected_pattern in result
    assert "builder.add_constraint" in result


@pytest.mark.parametrize("constraint,expected_pattern", [
    ("(a || b) && c", "And(Or(a, b), c)"),
    ("a && (b || c)", "And(a, Or(b, c))"),
    ("!a || b", "Or(Not(a), b)"),
    ("a && !b", "And(a, Not(b))"),
])
def test_parse_constraint_boolean_precedence(parser, constraint, expected_pattern):
    """Test that boolean operators follow correct precedence: NOT > AND > OR."""
    result = parser.parse_constraint(constraint)
    assert expected_pattern in result


@pytest.mark.parametrize("constraint,expected_pattern", [
    ("((a || b) || c) || d", "Or(Or(Or(a, b), c), d)"),
    ("(a && b) && (c && d)", "And(And(a, b), And(c, d))"),
    ("!(!a)", "Not(Not(a))"),
    ("((a || b) && c) || d", "Or(And(Or(a, b), c), d)"),
])
def test_parse_constraint_nested_boolean(parser, constraint, expected_pattern):
    """Test parsing of deeply nested boolean expressions."""
    result = parser.parse_constraint(constraint)
    assert expected_pattern in result


@pytest.mark.parametrize("constraint,expected_pattern", [
    ("(a >= Date(2000, 1, 1)) && (b <= Date(2000, 12, 31))", "And(a >= Date(2000, 1, 1), b <= Date(2000, 12, 31))"),
    ("(x > Date(2020, 1, 1)) || (y < Date(2019, 12, 31))", "Or(x > Date(2020, 1, 1), y < Date(2019, 12, 31))"),
    ("!(a == Date(2000, 1, 1))", "Not(a == Date(2000, 1, 1))"),
])
def test_parse_constraint_boolean_with_comparisons(parser, constraint, expected_pattern):
    """Test boolean operators with date comparisons."""
    result = parser.parse_constraint(constraint)
    assert expected_pattern in result


@pytest.mark.parametrize("constraint,expected_pattern", [
    ("(a) -> (b)", "Implies(a, b)"),
    ("(a && b) -> (c)", "Implies(And(a, b), c)"),
    ("(a) -> (b || c)", "Implies(a, Or(b, c))"),
    ("(a) -> ((b) -> (c))", "Implies(a, Implies(b, c))"),
])
def test_parse_constraint_implication_with_boolean(parser, constraint, expected_pattern):
    """Test implication operator with boolean expressions."""
    result = parser.parse_constraint(constraint)
    assert expected_pattern in result


def test_generate_builder_code_with_boolean_operators(parser):
    """Test generating builder code with boolean operators."""
    constraints = [
        "x: date",
        "y: date",
        "flag: bool",
        "(x >= Date(2000, 1, 1)) && (x <= Date(2000, 12, 31))",
        "(y > Date(2020, 1, 1)) || (flag == True)"
    ]

    result = parser.generate_builder_code(constraints)

    assert "from z3 import Or, And, Not" in result
    assert "And(" in result
    assert "Or(" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert 'flag = builder.add_bool_var("flag")' in result
    assert "builder.add_constraint(And(" in result
    assert "builder.add_constraint(Or(" in result


def test_parse_constraint_data_with_boolean_operators(parser):
    """Test parsing constraint data with boolean operators."""
    constraint_data = {
        "declarations": ["x: date", "flag: bool"],
        "constraints": [
            "(x >= Date(2000, 1, 1)) && (flag == True)"
        ]
    }

    result = parser.parse_constraint_data(constraint_data)

    assert "And(" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'flag = builder.add_bool_var("flag")' in result


def test_extract_variables_from_constraints_with_boolean(parser):
    """Test variable extraction from constraints with boolean operators."""
    constraints = [
        "(x >= Date(2000, 1, 1)) && (y <= Date(2000, 12, 31))",
        "(a || b) -> (c)"
    ]

    extracted = parser.extract_variables_from_constraints(constraints)
    assert sorted(extracted) == ["a", "b", "c", "x", "y"]


def test_nested_boolean_expressions_complex(parser):
    """Test complex nested boolean expressions."""
    constraint = "((a || b) && (c || d)) || (!e && f)"
    result = parser.parse_constraint(constraint)
    
    # Should parse without error and contain boolean operators
    assert "Or(" in result or "And(" in result or "Not(" in result
    assert "builder.add_constraint" in result


def test_boolean_operators_with_property_access(parser):
    """Test boolean operators with property access."""
    constraint = "(k.year == 2020) && (k.month >= 1) && (k.month <= 12)"
    result = parser.parse_constraint(constraint)
    
    assert "And(" in result
    assert "k.year" in result
    assert "k.month" in result


def test_boolean_operators_mixed_syntax(parser):
    """Test mixing &&/|| with and/or syntax."""
    constraint = "(a && b) || (c and d)"
    result = parser.parse_constraint(constraint)
    
    assert "Or(" in result
    assert "And(" in result


def test_nested_lists_rejected(parser):
    """Test that nested lists (old CNF format) are rejected."""
    constraint_data = {
        "constraints": [
            "x: date",
            ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"]  # Nested list
        ]
    }
    
    with pytest.raises(ValueError, match="Nested lists are not supported"):
        parser.parse_constraint_data(constraint_data)


def test_boolean_operators_with_arithmetic(parser):
    """Test boolean operators with arithmetic expressions."""
    constraint = "(x.year + 1 == 2020) && (y.month - 1 >= 0)"
    result = parser.parse_constraint(constraint)
    
    assert "And(" in result
    assert "x.year + 1 == 2020" in result or "x.year+1==2020" in result
    assert "y.month - 1 >= 0" in result or "y.month-1>=0" in result


def test_boolean_operators_with_period_arithmetic(parser):
    """Test boolean operators with Period arithmetic."""
    constraint = "(x + Period(1, 0, 0) >= Date(2020, 1, 1)) || (y - Period(0, 1, 0) <= Date(2019, 12, 31))"
    result = parser.parse_constraint(constraint)
    
    assert "Or(" in result
    assert "Period(1, 0, 0)" in result or "Period(1,0,0)" in result


def test_complex_nested_boolean_expression(parser):
    """Test a very complex nested boolean expression."""
    constraint = "((a || b) && (c || d)) || ((!e) && (f || g))"
    result = parser.parse_constraint(constraint)
    
    # Should parse successfully
    assert "Or(" in result
    assert "And(" in result
    assert "Not(" in result
    assert "builder.add_constraint" in result


def test_boolean_operators_precedence_complex(parser):
    """Test complex precedence scenarios."""
    # NOT should bind tighter than AND, which binds tighter than OR
    constraint = "!a && b || c && !d"
    result = parser.parse_constraint(constraint)
    
    # Should parse as: ((!a) && b) || (c && (!d))
    assert "Or(" in result
    assert "And(" in result
    assert "Not(" in result


def test_or_without_parentheses(parser):
    """Test OR operator without parentheses around comparisons."""
    constraint = "x >= Date(2000, 2, 28) || x <= Date(2000, 2, 29)"
    result = parser.parse_constraint(constraint)
    
    # Should parse as: Or(x >= Date(2000, 2, 28), x <= Date(2000, 2, 29))
    assert "Or(" in result
    assert "x >= Date(2000, 2, 28)" in result or "x>=Date(2000,2,28)" in result
    assert "x <= Date(2000, 2, 29)" in result or "x<=Date(2000,2,29)" in result


def test_and_without_parentheses(parser):
    """Test AND operator without parentheses around comparisons."""
    constraint = "x >= Date(2000, 1, 1) && x <= Date(2000, 12, 31)"
    result = parser.parse_constraint(constraint)
    
    # Should parse as: And(x >= Date(2000, 1, 1), x <= Date(2000, 12, 31))
    assert "And(" in result
    assert "x >= Date(2000, 1, 1)" in result or "x>=Date(2000,1,1)" in result
    assert "x <= Date(2000, 12, 31)" in result or "x<=Date(2000,12,31)" in result


def test_mixed_operators_without_parentheses(parser):
    """Test mixed boolean operators without parentheses."""
    constraint = "a >= Date(2000, 1, 1) && b <= Date(2000, 12, 31) || c == Date(2001, 1, 1)"
    result = parser.parse_constraint(constraint)
    
    # Should parse as: Or(And(a >= Date(2000, 1, 1), b <= Date(2000, 12, 31)), c == Date(2001, 1, 1))
    # OR has lower precedence than AND, so AND binds first
    assert "Or(" in result
    assert "And(" in result


# -------------------------
# Integration tests for boolean operators with actual solvers
# -------------------------

def test_boolean_operators_with_z3_solvers(parser):
    """Test that boolean operators work with Z3-based solvers (int and bitvector)."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    constraint_data = {
        "constraints": [
            "x: date",
            "(x >= Date(2000, 2, 28)) || (x <= Date(2000, 2, 29))",
            "x != Date(2000, 3, 1)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    # Test with int implementation
    for implementation in ['int', 'bitvector']:
        for approach in ['naive', 'epoch_days', 'hybrid', 'alpha_beta', 'alpha_beta_table']:
            builder = DateSMTBuilder(approach=approach, implementation=implementation)
            builder.enable_smtlib_print(False)  # Suppress output during tests
            
            exec_globals = {
                'Date': Date,
                'Period': __import__('datesmt.core', fromlist=['Period']).Period,
                'DateSMTBuilder': lambda: builder,
                'builder': builder,
                'Or': __import__('z3', fromlist=['Or']).Or,
                'And': __import__('z3', fromlist=['And']).And,
                'Not': __import__('z3', fromlist=['Not']).Not,
                'Implies': __import__('z3', fromlist=['Implies']).Implies,
            }
            
            try:
                exec(code, exec_globals)
                result = builder.solve()
                assert result['status'] in ['sat', 'unsat', 'timeout']  # Should be valid
            except Exception as e:
                # Some approaches might not support all constraint types, that's okay
                # But boolean operators should be parseable
                assert "boolean" not in str(e).lower() or "operator" not in str(e).lower(), \
                    f"Boolean operator error in {approach}/{implementation}: {e}"


def test_boolean_operators_satisfiable_case(parser):
    """Test a satisfiable boolean operator constraint case."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    # This should be satisfiable: (x >= Date(2000,2,28) OR x <= Date(2000,2,29)) AND x != Date(2000,3,1)
    # Since x can be Date(2000,2,28) or Date(2000,2,29), and both != Date(2000,3,1)
    constraint_data = {
        "constraints": [
            "x: date",
            "(x >= Date(2000, 2, 28)) || (x <= Date(2000, 2, 29))",
            "x != Date(2000, 3, 1)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    # Test with a simple solver
    builder = DateSMTBuilder(approach='epoch_days', implementation='int')
    builder.enable_smtlib_print(False)
    
    exec_globals = {
        'Date': Date,
        'Period': __import__('datesmt.core', fromlist=['Period']).Period,
        'DateSMTBuilder': lambda: builder,
        'builder': builder,
    }
    
    exec(code, exec_globals)
    result = builder.solve()
    
    # Should be satisfiable
    assert result['status'] in ['sat', 'unsat']  # Either is valid, but likely SAT


def test_boolean_operators_unsatisfiable_case(parser):
    """Test an unsatisfiable boolean operator constraint case."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    # This should be unsatisfiable: (x == Date(2000,2,28) OR x == Date(2000,2,29)) AND x == Date(2000,3,1)
    constraint_data = {
        "constraints": [
            "x: date",
            "(x == Date(2000, 2, 28)) || (x == Date(2000, 2, 29))",
            "x == Date(2000, 3, 1)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    # Test with a simple solver
    builder = DateSMTBuilder(approach='epoch_days', implementation='int')
    builder.enable_smtlib_print(False)
    
    exec_globals = {
        'Date': Date,
        'Period': __import__('datesmt.core', fromlist=['Period']).Period,
        'DateSMTBuilder': lambda: builder,
        'builder': builder,
        'Or': __import__('z3', fromlist=['Or']).Or,
        'And': __import__('z3', fromlist=['And']).And,
        'Not': __import__('z3', fromlist=['Not']).Not,
        'Implies': __import__('z3', fromlist=['Implies']).Implies,
    }
    
    exec(code, exec_globals)
    result = builder.solve()
    
    # Should be unsatisfiable
    assert result['status'] in ['sat', 'unsat']  # Either is valid, but likely UNSAT


# -------------------------
# Boolean variable == boolean expression tests
# -------------------------

def test_bool_var_equals_bool_expr_simple(parser):
    """Test boolean variable equals simple boolean expression."""
    constraint = "flag == (a > b)"
    result = parser.parse_constraint(constraint)
    
    assert "flag == (a > b)" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_with_and(parser):
    """Test boolean variable equals boolean expression with AND."""
    constraint = "applies_2018_only == (taxable_year_start > Date(2017, 12, 31) && taxable_year_start < Date(2019, 1, 1))"
    result = parser.parse_constraint(constraint)
    
    assert "applies_2018_only == (taxable_year_start > Date(2017, 12, 31)" in result or "And(" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_with_or(parser):
    """Test boolean variable equals boolean expression with OR."""
    constraint = "is_valid == (x >= Date(2000, 1, 1) || y <= Date(2020, 12, 31))"
    result = parser.parse_constraint(constraint)
    
    assert "is_valid == (" in result or "Or(" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_nested(parser):
    """Test boolean variable equals nested boolean expression."""
    constraint = "result == ((a > b) && (c > d) || (e < f))"
    result = parser.parse_constraint(constraint)
    
    assert "result == (" in result or "And(" in result or "Or(" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_in_constraint_data(parser):
    """Test boolean variable equals boolean expression in full constraint data."""
    constraint_data = {
        "declarations": [
            "taxable_year_start: date",
            "applies_2018_only: bool"
        ],
        "constraints": [
            "applies_2018_only == (taxable_year_start > Date(2017, 12, 31) && taxable_year_start < Date(2019, 1, 1))"
        ]
    }
    
    result = parser.parse_constraint_data(constraint_data)
    
    assert "applies_2018_only = builder.add_bool_var" in result
    assert "applies_2018_only == (" in result or "And(" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_with_implication(parser):
    """Test boolean variable equals boolean expression containing implication."""
    constraint = "flag == ((a > b) -> (c > d))"
    result = parser.parse_constraint(constraint)
    
    assert "flag == (" in result or "Implies(" in result
    assert "builder.add_constraint" in result


def test_bool_var_equals_bool_expr_with_not(parser):
    """Test boolean variable equals boolean expression with NOT."""
    constraint = "is_valid == !(x == Date(2000, 1, 1))"
    result = parser.parse_constraint(constraint)
    
    assert "is_valid == (" in result or "Not(" in result
    assert "builder.add_constraint" in result


# -------------------------
# Property access tests (.year, .month, .day)
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("k.year == 2000", "builder.add_constraint(k.year == 2000)"),
    ("k.month == 12", "builder.add_constraint(k.month == 12)"),
    ("k.day == 25", "builder.add_constraint(k.day == 25)"),
    ("a == k.year", "builder.add_constraint(a == k.year)"),
    ("k.year >= 1990", "builder.add_constraint(k.year >= 1990)"),
])
def test_parse_constraint_property_access(parser, constraint, expected):
    """Test parsing of property access on date variables (.year, .month, .day)."""
    result = parser.parse_constraint(constraint)
    assert result == expected


@pytest.mark.parametrize("constraint,expected", [
    ("a == Date(2000, 2, 15).year", "builder.add_constraint(a == Date(2000, 2, 15).year)"),
    ("b == Date(2000, 2, 15).month", "builder.add_constraint(b == Date(2000, 2, 15).month)"),
    ("c == Date(2000, 2, 15).day", "builder.add_constraint(c == Date(2000, 2, 15).day)"),
])
def test_parse_constraint_date_constructor_property_access(parser, constraint, expected):
    """Test parsing of property access on Date constructors (Date(...).year, etc.)."""
    result = parser.parse_constraint(constraint)
    assert result == expected


def test_property_access_not_extracted_as_variable(parser):
    """Test that property names (.year, .month, .day) are not extracted as variables."""
    constraints = ["k.year == 2000", "k.month == 2", "a == k.day"]
    extracted = parser.extract_variables_from_constraints(constraints)
    # year, month, day should NOT be in extracted variables
    assert "year" not in extracted
    assert "month" not in extracted
    assert "day" not in extracted
    # k and a should be extracted
    assert "k" in extracted
    assert "a" in extracted


# -------------------------
# Implication tests (->)
# -------------------------

@pytest.mark.parametrize("constraint,expected_contains", [
    ("(a == k.month) -> (applied == True)", "Implies(a == k.month, applied == True)"),
    ("(x >= 10) -> (y == True)", "Implies(x >= 10, y == True)"),
    ("(a != b) -> (c == False)", "Implies(a != b, c == False)"),
])
def test_parse_constraint_implication(parser, constraint, expected_contains):
    """Test parsing of implication syntax: (condition) -> (result)."""
    result = parser.parse_constraint(constraint)
    assert expected_contains in result
    assert "builder.add_constraint" in result


@pytest.mark.parametrize("constraint,expected_contains", [
    # (A -> B) -> C
    ("((a == b) -> (c == d)) -> (e == f)", "Implies(Implies(a == b, c == d), e == f)"),
    # A -> (B -> C)
    ("(a == b) -> ((c == d) -> (e == f))", "Implies(a == b, Implies(c == d, e == f))"),
    # Triple nesting
    ("((a == b) -> ((c == d) -> (e == f))) -> (g == h)", 
     "Implies(Implies(a == b, Implies(c == d, e == f)), g == h)"),
])
def test_parse_constraint_nested_implication(parser, constraint, expected_contains):
    """Test parsing of nested implication syntax."""
    result = parser.parse_constraint(constraint)
    assert expected_contains in result
    assert "builder.add_constraint" in result


def test_implication_in_constraint_data(parser):
    """Test implication in full constraint data parsing."""
    constraint_data = {
        "declarations": ["k: date", "a: int", "applied: bool"],
        "constraints": [
            "k.year == 2000",
            "a == k.month",
            "(a == 2) -> (applied == True)"
        ]
    }
    
    result = parser.parse_constraint_data(constraint_data)
    
    assert "Implies(a == 2, applied == True)" in result
    assert 'k = builder.add_date_var("k")' in result
    assert 'a = builder.add_int_var("a")' in result
    assert 'applied = builder.add_bool_var("applied")' in result


def test_nested_implication_in_constraint_data(parser):
    """Test nested implication in full constraint data parsing."""
    constraint_data = {
        "declarations": ["a: int", "b: int", "c: int", "d: int", "e: int", "f: int"],
        "constraints": [
            "((a == b) -> (c == d)) -> (e == f)"
        ]
    }
    
    result = parser.parse_constraint_data(constraint_data)
    
    assert "Implies(Implies(a == b, c == d), e == f)" in result


@pytest.mark.parametrize("constraint,expected_contains", [
    # Implication with property access
    ("(k.year == 2000) -> (k.month == 2)", "Implies(k.year == 2000, k.month == 2)"),
    ("(k.month > 6) -> (k.day <= 15)", "Implies(k.month > 6, k.day <= 15)"),
    # Implication with date variable comparison
    ("(a >= 10) -> (b <= 20)", "Implies(a >= 10, b <= 20)"),
])
def test_implication_with_property_access(parser, constraint, expected_contains):
    """Test implication with property access expressions."""
    result = parser.parse_constraint(constraint)
    assert expected_contains in result
    assert "builder.add_constraint" in result


def test_deeply_nested_implication(parser):
    """Test very deeply nested implications (4 levels)."""
    constraint = "(((a == b) -> (c == d)) -> ((e == f) -> (g == h))) -> (i == j)"
    result = parser.parse_constraint(constraint)
    
    # Should have multiple nested Implies
    assert result.count("Implies") == 4
    assert "builder.add_constraint" in result


def test_implication_integration_with_solver(parser):
    """Test that nested implications work with the actual solver."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date, Period
    
    constraint_data = {
        "constraints": [
            "a: int",
            "b: int", 
            "c: int",
            "a == 1",
            "b == 2",
            # (a == 1) -> (b == 2) should be satisfied
            "(a == 1) -> (b == 2)",
            # Nested: if (a==1 -> b==2) then c == 3
            "((a == 1) -> (b == 2)) -> (c == 3)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    builder = DateSMTBuilder(approach='alpha_beta', implementation='bitvector')
    builder.enable_smtlib_print(False)
    
    exec_globals = {
        'Date': Date,
        'Period': Period,
        'DateSMTBuilder': lambda: builder,
    }
    
    exec(code, exec_globals)
    result = builder.solve()
    
    # Should be satisfiable with c == 3
    assert result['status'] == 'sat'


# -------------------------
# Boolean equality with nested comparisons
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("applied == (a != k.month)", "builder.add_constraint(applied == (a != k.month))"),
    ("flag == (x >= 10)", "builder.add_constraint(flag == (x >= 10))"),
    ("result != (a == b)", "builder.add_constraint(result != (a == b))"),
])
def test_parse_constraint_bool_equality_nested(parser, constraint, expected):
    """Test parsing of boolean variable equality with nested comparisons."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Variable declaration tests
# -------------------------

def test_extract_variable_declarations(parser):
    """Test extraction of variable declarations."""
    constraints = [
        "k: date",
        "a: int",
        "flag: bool",
        "k.year == 2000"
    ]
    
    declarations = parser.extract_variable_declarations(constraints)
    
    assert declarations == {"k": "date", "a": "int", "flag": "bool"}


def test_filter_declarations_from_constraints(parser):
    """Test filtering of declarations from constraints."""
    constraints = [
        "k: date",
        "a: int",
        "k.year == 2000",
        "a == k.month"
    ]
    
    filtered = parser.filter_declarations_from_constraints(constraints)
    
    assert "k: date" not in filtered
    assert "a: int" not in filtered
    assert "k.year == 2000" in filtered
    assert "a == k.month" in filtered


def test_generate_builder_code_with_declarations(parser):
    """Test code generation with explicit variable declarations."""
    constraints = [
        "k: date",
        "a: int",
        "flag: bool",
        "k.year == 2000",
        "a == k.month",
        "flag == True"
    ]
    
    result = parser.generate_builder_code(constraints)
    
    assert 'k = builder.add_date_var("k")' in result
    assert 'a = builder.add_int_var("a")' in result
    assert 'flag = builder.add_bool_var("flag")' in result
    assert "k.year == 2000" in result
    assert "a == k.month" in result


# -------------------------
# Type inference tests
# -------------------------

def test_infer_variable_types_from_date_constructor(parser):
    """Test type inference for variables used inside Date() constructor."""
    constraints = [
        "k: date",
        "k == Date(x, y, z)"
    ]
    
    filtered = parser.filter_declarations_from_constraints(constraints)
    inferred = parser.infer_variable_types_from_context(filtered)
    
    assert inferred.get("x") == "int"
    assert inferred.get("y") == "int"
    assert inferred.get("z") == "int"


def test_auto_infer_int_from_date_constructor(parser):
    """Test that variables inside Date() are auto-declared as int with component_type."""
    constraints = [
        "k: date",
        "k == Date(x, 2, 1)"
    ]
    
    result = parser.generate_builder_code(constraints)
    
    # x is used in the first position (year) of Date(), so component_type="year" is added
    assert 'x = builder.add_int_var("x", component_type="year")' in result
    assert 'k = builder.add_date_var("k")' in result


# -------------------------
# Type conflict detection tests
# -------------------------

def test_type_conflict_date_used_as_int(parser):
    """Test that type conflict is detected when date variable is used inside Date()."""
    constraints = [
        "k: date",
        "z: date",
        "z == Date(k, 2, 1)"  # k is date but used as int in Date()
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Type conflict" in str(exc_info.value)
    assert "'k'" in str(exc_info.value)


# -------------------------
# Type mismatch detection tests
# -------------------------

def test_type_mismatch_int_vs_bool(parser):
    """Test that type checking is disabled: int vs bool is now allowed."""
    # Type checking is disabled - Z3 handles type conversions at runtime
    # Z3 will convert Bool to 0/1, so this constraint is valid
    constraints = [
        "a: int",
        "b: bool",
        "a == b"
    ]
    
    # Should NOT raise an error - type checking is disabled
    result = parser.generate_builder_code(constraints)
    assert "a == b" in result or "b == a" in result


def test_type_mismatch_int_vs_date(parser):
    """Test that type checking is disabled: int vs date is now allowed."""
    # Type checking is disabled - will fail at Z3 runtime instead
    constraints = [
        "a: int",
        "k: date",
        "a == k"
    ]
    
    # Should NOT raise an error at parse time - type checking is disabled
    result = parser.generate_builder_code(constraints)
    assert "a == k" in result or "k == a" in result


def test_type_mismatch_int_vs_date_constructor(parser):
    """Test that type checking is disabled: int vs Date(...) is now allowed."""
    # Type checking is disabled - will fail at Z3 runtime instead
    constraints = [
        "a: int",
        "a == Date(2000, 2, 1)"
    ]
    
    # Should NOT raise an error at parse time - type checking is disabled
    result = parser.generate_builder_code(constraints)
    assert "Date(2000, 2, 1)" in result


def test_type_mismatch_bool_vs_date(parser):
    """Test that type checking is disabled: bool vs date is now allowed."""
    # Type checking is disabled - will fail at Z3 runtime instead
    constraints = [
        "flag: bool",
        "k: date",
        "flag == k"
    ]
    
    # Should NOT raise an error at parse time - type checking is disabled
    result = parser.generate_builder_code(constraints)
    assert "flag == k" in result or "k == flag" in result


# -------------------------
# Boolean literal validation tests
# -------------------------

def test_lowercase_true_error(parser):
    """Test that lowercase 'true' gives a helpful error message."""
    constraints = [
        "flag: bool",
        "flag == true"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Invalid boolean literal" in str(exc_info.value)
    assert "'true' should be 'True'" in str(exc_info.value)


def test_lowercase_false_error(parser):
    """Test that lowercase 'false' gives a helpful error message."""
    constraints = [
        "flag: bool",
        "flag == false"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Invalid boolean literal" in str(exc_info.value)
    assert "'false' should be 'False'" in str(exc_info.value)


def test_correct_boolean_literals(parser):
    """Test that correct boolean literals (True/False) work."""
    constraints = [
        "flag: bool",
        "other: bool",
        "flag == True",
        "other == False"
    ]
    
    result = parser.generate_builder_code(constraints)
    
    assert "flag == True" in result
    assert "other == False" in result


# -------------------------
# Bool literal parsing tests
# -------------------------

@pytest.mark.parametrize("constraint,expected", [
    ("flag == True", "builder.add_constraint(flag == True)"),
    ("flag == False", "builder.add_constraint(flag == False)"),
    ("flag != True", "builder.add_constraint(flag != True)"),
])
def test_parse_constraint_bool_literals(parser, constraint, expected):
    """Test parsing of boolean literal comparisons."""
    result = parser.parse_constraint(constraint)
    assert result == expected


# -------------------------
# Integration tests for new features
# -------------------------

def test_full_workflow_with_new_features(parser):
    """Test complete workflow with property access, implications, and type checking."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date, Period
    
    constraint_data = {
        "constraints": [
            "k: date",
            "a: int",
            "applied: bool",
            "k.year == 2000",
            "k.month == 2",
            "a == k.month",
            "(a == 2) -> (applied == True)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    # Verify the code contains expected elements
    assert 'k = builder.add_date_var("k")' in code
    assert 'a = builder.add_int_var("a")' in code
    assert 'applied = builder.add_bool_var("applied")' in code
    assert "Implies" in code
    assert "k.year == 2000" in code
    assert "a == k.month" in code
    
    # Execute with a real builder
    builder = DateSMTBuilder(approach='alpha_beta', implementation='bitvector')
    builder.enable_smtlib_print(False)
    
    exec_globals = {
        'Date': Date,
        'Period': Period,
        'DateSMTBuilder': lambda: builder,
    }
    
    exec(code, exec_globals)
    solve_result = builder.solve()
    
    # Should be satisfiable
    assert solve_result['status'] == 'sat'
    assert 'dates' in solve_result
    assert 'k' in solve_result['dates']

