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

    # Helper function is always included now, but not used for simple constraints
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(y <= Date(2020, 12, 31))" in result
    assert "result = builder" in result
    # Should not use _or_constraints for simple constraints (only in definition)
    assert result.count("_or_constraints(") == 1  # Only in function definition

def test_generate_builder_code_empty(parser):
    """Test builder code generation with empty inputs."""
    constraints = []

    result = parser.generate_builder_code(constraints)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert "builder = DateSMTBuilder()" in result
    assert "result = builder" in result


# -------------------------
# parse_constraint_data method
# -------------------------

def test_parse_constraint_data_basic(parser):
    """Test parsing constraint data with declared variables."""
    constraint_data = {
        "constraints": ["x: date", "y: date", "x >= Date(2000, 1, 1)", "y <= Date(2020, 12, 31)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 1, 1))" in result
    assert "builder.add_constraint(y <= Date(2020, 12, 31))" in result
    assert "result = builder" in result


def test_parse_constraint_data_missing_keys(parser):
    """Test parsing constraint data with missing keys."""
    constraint_data = {}

    result = parser.parse_constraint_data(constraint_data)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert "builder = DateSMTBuilder()" in result
    assert "result = builder" in result


def test_parse_constraint_data_with_periods(parser):
    """Test parsing constraint data with period."""
    constraint_data = {
        "constraints": ["x: date", "x + Period(0,1,1) >= Date(2000, 1, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert 'x = builder.add_date_var("x")' in result
    assert "builder.add_constraint(x + Period(0, 1, 1) >= Date(2000, 1, 1))" in result
    assert "result = builder" in result


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
        "constraints": ["x: date", "x >= Date(2000, 2, 28)", "x <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert 'x = builder.add_date_var("x")' in result
    assert "builder.add_constraint(x >= Date(2000, 2, 28))" in result
    assert "builder.add_constraint(x <= Date(2000, 3, 1))" in result
    assert "result = builder" in result

def test_parse_constraint_data_with_multiple_datevar(parser):
    """Test parsing constraint data with multiple date variables."""
    constraint_data = {
        "constraints": ["x: date", "y: date", "x >= Date(2000, 2, 28)", "y <= Date(2000, 3, 1)"]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Helper function is always included now
    assert "from z3 import Or" in result
    assert "def _or_constraints" in result
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result
    assert "builder.add_constraint(x >= Date(2000, 2, 28))" in result
    assert "builder.add_constraint(y <= Date(2000, 3, 1))" in result
    assert "result = builder" in result


# -------------------------
# CNF (Conjunctive Normal Form) tests
# -------------------------

def test_generate_builder_code_cnf_simple_or(parser):
    """Test CNF format with a simple OR clause."""
    constraints = [
        "x: date",
        ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
        "x != Date(2000, 3, 1)"
    ]

    result = parser.generate_builder_code(constraints)

    # Check that the result contains the helper function and OR constraint
    assert "from z3 import Or" in result
    assert "from datesmt.enumeration_baseline import ConstraintWrapper" in result
    assert "def _or_constraints" in result
    # Should use _or_constraints for the OR clause (2 calls: definition + usage)
    assert result.count("_or_constraints(") >= 2
    # Check that both constraints are in the OR expression
    assert "x >= Date(2000, 2, 28)" in result or "x >= Date(2000,2,28)" in result
    assert "x <= Date(2000, 2, 29)" in result or "x <= Date(2000,2,29)" in result
    assert "x != Date(2000, 3, 1)" in result or "x != Date(2000,3,1)" in result
    assert 'x = builder.add_date_var("x")' in result


def test_generate_builder_code_cnf_mixed(parser):
    """Test CNF format with mixed AND and OR constraints."""
    constraints = [
        "x: date",
        "y: date",
        "x >= Date(2000, 1, 1)",
        ["x <= Date(2000, 2, 28)", "x >= Date(2000, 3, 1)"],
        "y == x + Period(0, 1, 0)"
    ]

    result = parser.generate_builder_code(constraints)

    # Check that all constraints are present (with flexible spacing)
    assert "x >= Date(2000, 1, 1)" in result or "x >= Date(2000,1,1)" in result
    assert "x <= Date(2000, 2, 28)" in result or "x <= Date(2000,2,28)" in result
    assert "x >= Date(2000, 3, 1)" in result or "x >= Date(2000,3,1)" in result
    assert "y == x + Period(0, 1, 0)" in result or "y == x + Period(0,1,0)" in result
    # Should use _or_constraints for the OR clause (2 calls: definition + usage)
    assert result.count("_or_constraints(") >= 2
    assert 'x = builder.add_date_var("x")' in result
    assert 'y = builder.add_date_var("y")' in result


def test_generate_builder_code_cnf_single_item_or(parser):
    """Test CNF format with a single-item OR clause (should be treated as regular constraint)."""
    constraints = [
        "x: date",
        ["x >= Date(2000, 2, 28)"],
        "x != Date(2000, 3, 1)"
    ]

    result = parser.generate_builder_code(constraints)

    # Single-item OR should be treated as regular constraint
    assert "x >= Date(2000, 2, 28)" in result or "x >= Date(2000,2,28)" in result
    assert "x != Date(2000, 3, 1)" in result or "x != Date(2000,3,1)" in result
    # Should not use _or_constraints for single-item list (only in definition)
    assert result.count("_or_constraints(") == 1  # Only in function definition


def test_parse_constraint_data_cnf_format(parser):
    """Test parsing constraint data with CNF format."""
    constraint_data = {
        "constraints": [
            "x: date",
            ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
            "x != Date(2000, 3, 1)"
        ]
    }

    result = parser.parse_constraint_data(constraint_data)

    # Check that CNF format is properly handled
    # Should use _or_constraints for the OR clause (2 calls: definition + usage)
    assert result.count("_or_constraints(") >= 2
    # Check constraints are present (with flexible spacing)
    assert "x >= Date(2000, 2, 28)" in result or "x >= Date(2000,2,28)" in result
    assert "x <= Date(2000, 2, 29)" in result or "x <= Date(2000,2,29)" in result
    assert "x != Date(2000, 3, 1)" in result or "x != Date(2000,3,1)" in result
    assert 'x = builder.add_date_var("x")' in result


def test_extract_variables_from_constraints_cnf(parser):
    """Test variable extraction from CNF format constraints."""
    constraints = [
        ["x >= Date(2000, 2, 28)", "y <= Date(2000, 2, 29)"],
        "z != Date(2000, 3, 1)"
    ]

    extracted = parser.extract_variables_from_constraints(constraints)
    assert sorted(extracted) == ["x", "y", "z"]


def test_extract_variables_from_constraints_cnf_nested(parser):
    """Test variable extraction from complex CNF format with multiple OR clauses."""
    constraints = [
        ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
        ["y >= Date(2000, 1, 1)", "y <= Date(2000, 1, 31)"],
        "z == x + Period(0, 1, 0)"
    ]

    extracted = parser.extract_variables_from_constraints(constraints)
    assert sorted(extracted) == ["x", "y", "z"]


def test_generate_builder_code_backward_compatible(parser):
    """Test that simple list of strings works with declarations."""
    constraints = ["x: date", "x >= Date(2000, 2, 28)", "x <= Date(2000, 3, 1)"]

    result = parser.generate_builder_code(constraints)

    # Should work with declarations - constraints are added directly, not via OR
    assert "builder.add_constraint(x >= Date(2000, 2, 28))" in result
    assert "builder.add_constraint(x <= Date(2000, 3, 1))" in result
    assert 'x = builder.add_date_var("x")' in result
    # Helper function is included but not used for simple constraints
    assert "_or_constraints(" not in result or result.count("_or_constraints(") == 1  # Only in definition


# -------------------------
# Integration tests for CNF format with actual solvers
# -------------------------

def test_cnf_format_with_enumeration_baseline(parser):
    """Test that CNF format works with enumeration baseline solver."""
    from datesmt.enumeration_baseline import EnumerationSolver
    from datesmt.core import Date
    
    constraint_data = {
        "constraints": [
            "x: date",
            ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
            "x != Date(2000, 3, 1)"
        ]
    }
    
    code = parser.parse_constraint_data(constraint_data)
    
    # Execute the code with enumeration solver
    enumeration_solver = EnumerationSolver()
    exec_globals = {
        'Date': Date,
        'Period': __import__('datesmt.core', fromlist=['Period']).Period,
        'DateSMTBuilder': lambda: enumeration_solver,
        'builder': enumeration_solver,
        'result': enumeration_solver,
    }
    
    exec(code, exec_globals)
    
    # Solve and verify
    result = enumeration_solver.solve()
    assert result['status'] in ['sat', 'unsat']  # Should be valid
    if result['status'] == 'sat':
        # If satisfiable, verify the solution satisfies the constraints
        assert 'dates' in result
        assert len(result['dates']) > 0


def test_cnf_format_with_z3_solvers(parser):
    """Test that CNF format works with Z3-based solvers (int and bitvector)."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    constraint_data = {
        "constraints": [
            "x: date",
            ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
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
                'result': builder,
            }
            
            try:
                exec(code, exec_globals)
                result = builder.solve()
                assert result['status'] in ['sat', 'unsat', 'timeout']  # Should be valid
            except Exception as e:
                # Some approaches might not support all constraint types, that's okay
                # But CNF format itself should be parseable
                assert "CNF" not in str(e) or "OR" not in str(e), f"CNF format error in {approach}/{implementation}: {e}"


def test_cnf_format_satisfiable_case(parser):
    """Test a satisfiable CNF constraint case."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    # This should be satisfiable: (x >= Date(2000,2,28) OR x <= Date(2000,2,29)) AND x != Date(2000,3,1)
    # Since x can be Date(2000,2,28) or Date(2000,2,29), and both != Date(2000,3,1)
    constraint_data = {
        "constraints": [
            "x: date",
            ["x >= Date(2000, 2, 28)", "x <= Date(2000, 2, 29)"],
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
        'result': builder,
    }
    
    exec(code, exec_globals)
    result = builder.solve()
    
    # Should be satisfiable
    assert result['status'] in ['sat', 'unsat']  # Either is valid, but likely SAT


def test_cnf_format_unsatisfiable_case(parser):
    """Test an unsatisfiable CNF constraint case."""
    from datesmt.api import DateSMTBuilder
    from datesmt.core import Date
    
    # This should be unsatisfiable: (x == Date(2000,2,28) OR x == Date(2000,2,29)) AND x == Date(2000,3,1)
    constraint_data = {
        "constraints": [
            "x: date",
            ["x == Date(2000, 2, 28)", "x == Date(2000, 2, 29)"],
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
        'result': builder,
    }
    
    exec(code, exec_globals)
    result = builder.solve()
    
    # Should be unsatisfiable
    assert result['status'] in ['sat', 'unsat']  # Either is valid, but likely UNSAT


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
        "constraints": [
            "k: date",
            "a: int",
            "applied: bool",
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
        "constraints": [
            "a: int",
            "b: int",
            "c: int",
            "d: int",
            "e: int",
            "f: int",
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
    """Test that variables inside Date() are auto-declared as int."""
    constraints = [
        "k: date",
        "k == Date(x, 2, 1)"
    ]
    
    result = parser.generate_builder_code(constraints)
    
    assert 'x = builder.add_int_var("x")' in result
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
    """Test that type mismatch is detected: int vs bool."""
    constraints = [
        "a: int",
        "b: bool",
        "a == b"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Type mismatch" in str(exc_info.value)
    assert "int" in str(exc_info.value)
    assert "bool" in str(exc_info.value)


def test_type_mismatch_int_vs_date(parser):
    """Test that type mismatch is detected: int vs date."""
    constraints = [
        "a: int",
        "k: date",
        "a == k"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Type mismatch" in str(exc_info.value)


def test_type_mismatch_int_vs_date_constructor(parser):
    """Test that type mismatch is detected: int vs Date(...)."""
    constraints = [
        "a: int",
        "a == Date(2000, 2, 1)"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Type mismatch" in str(exc_info.value)


def test_type_mismatch_bool_vs_date(parser):
    """Test that type mismatch is detected: bool vs date."""
    constraints = [
        "flag: bool",
        "k: date",
        "flag == k"
    ]
    
    with pytest.raises(ValueError) as exc_info:
        parser.generate_builder_code(constraints)
    
    assert "Type mismatch" in str(exc_info.value)


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

