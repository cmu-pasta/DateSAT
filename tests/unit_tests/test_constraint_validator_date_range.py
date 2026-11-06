"""Validator semantics for Date + Period near the ends of the year range.

Every encoding computes Date + Period as: add years and months, clamp to the end of
the month, add days. With python_bounds=True only the final result is bounded to
years 1..9999, and that bound is asserted globally. So the validator must

  * allow the mid-step (after years and months, before days) to leave 1..9999, and
  * with python_bounds=True, reject a model that pushes any Date + Period result
    outside 1..9999, wherever that expression sits (under a negation, in an unused
    disjunct), while
  * by default (unbounded) accept such a model and evaluate the result exactly.

Expected dates were derived by hand, shifting by 400 years (146097 days), after
which the Gregorian calendar repeats.
"""

from datesat.constraint_validator import validate_constraint_solution


def _code(date_vars, *constraints):
    lines = [
        "from z3 import Or, And, Not, Int, Bool, Implies",
        "builder = DateSATBuilder()",
    ]
    lines += [f'{v} = builder.add_date_var("{v}")' for v in date_vars]
    lines += [f"builder.add_constraint({c})" for c in constraints]
    return "\n".join(lines) + "\n"


def test_accepts_grammar_190_model_whose_mid_step_is_before_year_1():
    # grammar-190 from DateSATBench; hybrid_init_epoch returned this model. In (3),
    # 0009-02-28 - 10 years + 1 month = year -1, March 28; + 1000 days = 0001-12-22.
    code = _code(
        ["D0", "D1", "D2", "D3"],
        "D2 > (D3 - Period(3, 0, 0))",
        "D0 < Date(7171, 5, 25)",
        "D3 > (D0 + Period(-10, 1, 1000))",
        "D1 > Date(7171, 9, 7)",
        "D1 >= Date(7097, 4, 19)",
        "D3 <= ((D3 - Period(0, -10, 4)) - Period(0, -11, -1000))",
    )
    model = {
        "D0": "Date(9, 2, 28)",
        "D1": "Date(7171, 9, 8)",
        "D2": "Date(3096, 5, 29)",
        "D3": "Date(3099, 5, 28)",
    }
    ok, msg = validate_constraint_solution(code, model)
    assert ok, msg


def test_computes_result_exactly_when_mid_step_is_before_year_1():
    code = _code(["D0"], "D0 + Period(-10, 1, 1000) == Date(1, 12, 22)")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(9, 2, 28)"})
    assert ok, msg


def test_computes_result_exactly_when_mid_step_is_after_year_9999():
    # 9999-06-01 + 1 year = 10000-06-01; - 400 days = 9999-04-28.
    code = _code(["D0"], "D0 + Period(1, 0, -400) == Date(9999, 4, 28)")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(9999, 6, 1)"})
    assert ok, msg


def test_rejects_negation_of_true_comparison_with_mid_step_before_year_1():
    # D0 + Period(-10, 1, 1000) = 0001-12-22, which IS before 5000-01-01.
    code = _code(["D0"], "Not(D0 + Period(-10, 1, 1000) < Date(5000, 1, 1))")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(9, 2, 28)"}, python_bounds=True)
    assert not ok, msg


def test_rejects_model_whose_period_result_is_before_year_1_under_negation():
    # 0005-01-01 - 10 years = year -5: no encoding allows that result under python_bounds.
    code = _code(["D0"], "Not(D0 - Period(10, 0, 0) > Date(1, 1, 1))")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(5, 1, 1)"}, python_bounds=True)
    assert not ok, msg


def test_rejects_model_whose_period_result_is_out_of_range_in_unused_disjunct():
    code = _code(["D0"], "Or(D0 == Date(5, 1, 1), D0 - Period(10, 0, 0) < Date(1, 1, 1))")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(5, 1, 1)"}, python_bounds=True)
    assert not ok, msg


def test_in_range_period_still_clamps_to_end_of_month():
    # Guard for the rewrite: 2000-01-31 + 1 month clamps to 2000-02-29 (leap year), + 1 day
    # is 2000-03-01. From 2000-01-28 there is no clamp: 2000-02-28, + 1 day is 2000-02-29.
    code = _code(["D0"], "D0 + Period(0, 1, 1) == Date(2000, 3, 1)")
    assert validate_constraint_solution(code, {"D0": "Date(2000, 1, 31)"})[0]
    assert not validate_constraint_solution(code, {"D0": "Date(2000, 1, 28)"})[0]


def test_unbounded_accepts_period_result_before_year_1():
    # Default (unbounded): 0005-01-01 - 10 years = -0005-01-01, which is not > 0001-01-01,
    # so the negated comparison holds and the model is valid.
    code = _code(["D0"], "Not(D0 - Period(10, 0, 0) > Date(1, 1, 1))")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(5, 1, 1)"})
    assert ok, msg


def test_unbounded_evaluates_period_result_beyond_year_9999_exactly():
    code = _code(["D0"], "D0 + Period(1, 0, 0) == Date(10000, 2, 28)")
    assert validate_constraint_solution(code, {"D0": "Date(9999, 2, 28)"})[0]
    assert not validate_constraint_solution(code, {"D0": "Date(9999, 2, 27)"})[0]


def test_unbounded_accepts_model_values_outside_python_range():
    code = _code(["D0", "D1"], "D1 == D0 + Period(0, 0, 1)")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(-1, 12, 31)", "D1": "Date(0, 1, 1)"})
    assert ok, msg
    ok, msg = validate_constraint_solution(code, {"D0": "Date(-1, 12, 31)", "D1": "Date(0, 1, 1)"},
                                           python_bounds=True)
    assert not ok and "outside years 1..9999" in msg
