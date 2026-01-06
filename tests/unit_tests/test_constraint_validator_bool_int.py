from datesmt.constraint_validator import validate_constraint_solution


def test_validate_solution_with_bool_and_int_true():
    constraint_code = """
from z3 import Or, And, Not, Int, Bool, Implies
builder = DateSMTBuilder()
a = builder.add_int_var("a")
flag = builder.add_bool_var("flag")
builder.add_constraint(a == 3)
builder.add_constraint(flag == True)
"""
    ok, msg = validate_constraint_solution(constraint_code, {"a": 3, "flag": True})
    assert ok, msg


def test_validate_solution_with_bool_and_int_false():
    constraint_code = """
from z3 import Or, And, Not, Int, Bool, Implies
builder = DateSMTBuilder()
a = builder.add_int_var("a")
flag = builder.add_bool_var("flag")
builder.add_constraint(a == 3)
builder.add_constraint(flag == True)
"""
    ok, msg = validate_constraint_solution(constraint_code, {"a": 2, "flag": False})
    assert not ok

