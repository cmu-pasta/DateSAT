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
    "x",  # No comparison operator
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


@pytest.mark.parametrize("constraint_with_multiple_operators", [
    "x >= Date(2000, 1, 1) == Date(2001, 1, 1)",  # Multiple operators
])
def test_parse_constraint_multiple_operators(parser, constraint_with_multiple_operators):
    """Test that constraints with multiple operators are handled (may not raise error)."""
    # The current parser implementation may handle this by taking the first operator
    result = parser.parse_constraint(constraint_with_multiple_operators)
    assert "builder.add_constraint" in result


@pytest.mark.parametrize("constraint_with_incomplete_constructors", [
    "x >= Date(2000, 1)",  # Incomplete Date constructor
    "x >= Period(1, 0)",  # Incomplete Period constructor
    "x >= Date(2000, 1, 1, 1)",  # Too many Date arguments
    "x >= Period(1, 0, 0, 0)",  # Too many Period arguments
])
def test_parse_constraint_incomplete_constructors(parser, constraint_with_incomplete_constructors):
    """Test that incomplete constructors are handled (may not raise error)."""
    # The current parser implementation may handle this by passing through the text
    result = parser.parse_constraint(constraint_with_incomplete_constructors)
    assert "builder.add_constraint" in result


# -------------------------
# Description handling
# -------------------------

@pytest.mark.parametrize("constraint_with_description,expected", [
    ("x >= Date(2000, 1, 1), 'comment'", "builder.add_constraint(x >= Date(2000, 1, 1), 'comment')"),
    ("y <= Date(2020, 12, 31), 'another comment'", "builder.add_constraint(y <= Date(2020, 12, 31), 'another comment')"),
    ("z == Date(1999, 1, 1), 'test'", "builder.add_constraint(z == Date(1999, 1, 1), 'test')"),
])
def test_parse_constraint_with_descriptions(parser, constraint_with_description, expected):
    """Test that comments are properly preserved as descriptions in constraints."""
    result = parser.parse_constraint(constraint_with_description)
    assert result == expected


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
    constraints = ["x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]

    result = parser.generate_builder_code(constraints)

    expected_lines = [
        "builder = DateSMTBuilder()",
        'x = builder.add_date_var("x")',
        'y = builder.add_date_var("y")',
        "builder.add_constraint(x >= Date(2000, 1, 1))",
        "builder.add_constraint(y <= Date(2020, 12, 31))",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)

def test_generate_builder_code_empty(parser):
    """Test builder code generation with empty inputs."""
    constraints = []

    result = parser.generate_builder_code(constraints)

    expected_lines = [
        "builder = DateSMTBuilder()",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)


# -------------------------
# parse_constraint_data method
# -------------------------

def test_parse_constraint_data_basic(parser):
    """Test parsing constraint data with auto-extracted variables."""
    constraint_data = {
        "constraints": ["x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    expected_lines = [
        "builder = DateSMTBuilder()",
        'x = builder.add_date_var("x")',
        'y = builder.add_date_var("y")',
        "builder.add_constraint(x >= Date(2000, 1, 1))",
        "builder.add_constraint(y <= Date(2020, 12, 31))",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)


def test_parse_constraint_data_missing_keys(parser):
    """Test parsing constraint data with missing keys."""
    constraint_data = {}

    result = parser.parse_constraint_data(constraint_data)

    expected_lines = [
        "builder = DateSMTBuilder()",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)


def test_parse_constraint_data_with_periods(parser):
    """Test parsing constraint data with period."""
    constraint_data = {
        "constraints": ["x + Period(0,1,1) >= Date(2000, 1, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    expected_lines = [
        "builder = DateSMTBuilder()",
        'x = builder.add_date_var("x")',
        "builder.add_constraint(x + Period(0, 1, 1) >= Date(2000, 1, 1))",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)


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
    """Test the complete workflow from constraint data to executable code with auto-extraction."""
    constraint_data = {
        "constraints": [
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
    assert "result = builder" in result


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
        "Z13 == Period(0, 1, 0) + Period(0, 1, 0)"
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    # Variables are returned in alphabetical order
    # Z13 should not be extracted because the constraint is invalid (period comparison)
    assert extracted == ["x_23", "y_add_period"]

def test_auto_extract_variables_filters_keywords(parser):
    """Test that auto-extraction filters out keywords and constructors."""
    constraints = [
        "x >= Date(2000, 1, 1)",
        "y == x + Period(0, 1, 0)",
        "is_valid == True"
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    assert extracted == ["is_valid", "x", "y"]

def test_auto_extract_variables_skips_invalid_period_comparisons(parser):
    """Test that auto-extraction skips invalid period comparison constraints."""
    constraints = [
        "x >= Date(2000, 1, 1)",  # Valid: date comparison
        "y == x + Period(0, 1, 0)",  # Valid: date + period = date
        "y2 == Period(0, 1, 1) + x",  # Valid: period + date = date
        "z == Period(0, 1, 0) + Period(0, 1, 0)",  # Invalid: period operation
        "z1 == Period(0, 1, 0) - Period(0, 1, 0)",  # Invalid: period operation
        "z2 == Period(0, 1, 0) * 3",  # Invalid: period multiplication
        "z3 == 2 * Period(0, 1, 0)",  # Invalid: period multiplication
        "w != Period(0, 2, 0)",  # Invalid: period comparison
        "v == Period(0, 1, 0)"  # Invalid: period comparison
    ]
    extracted = parser.extract_variables_from_constraints(constraints)
    # Should only extract variables from valid constraints
    assert extracted == ["x", "y", "y2"]


def test_parse_constraint_data_with_one_datevar(parser):
    """Test parsing constraint data with one date variable."""
    constraint_data = {
        "constraints": ["x >= Date(2000, 2, 28)", "x <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    expected_lines = [
        "builder = DateSMTBuilder()",
        'x = builder.add_date_var("x")',
        "builder.add_constraint(x >= Date(2000, 2, 28))",
        "builder.add_constraint(x <= Date(2000, 3, 1))",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)

def test_parse_constraint_data_with_multiple_datevar(parser):
    """Test parsing constraint data with multiple date variables."""
    constraint_data = {
        "constraints": ["x >= Date(2000, 2, 28)", "y <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    expected_lines = [
        "builder = DateSMTBuilder()",
        'x = builder.add_date_var("x")',
        'y = builder.add_date_var("y")',
        "builder.add_constraint(x >= Date(2000, 2, 28))",
        "builder.add_constraint(y <= Date(2000, 3, 1))",
        "result = builder"
    ]

    assert result == "\n".join(expected_lines)

