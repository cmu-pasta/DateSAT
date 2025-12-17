##################################################
# Library imports
##################################################
import re
import datetime


##################################################
# Generator grammar
##################################################

<start> ::= <constraint_list>

# NOTE: Manually unrolled on purpose to generate more constraints!
<constraint_list> ::= <ten_constraints> | <nine_constraints> | <eight_constraints> | <seven_constraints> | <six_constraints> | <five_constraints>

<ten_constraints> ::= <nine_constraints> " ; " <constraint>
<nine_constraints> ::= <eight_constraints> " ; " <constraint>
<eight_constraints> ::= <seven_constraints> " ; " <constraint>
<seven_constraints> ::= <six_constraints> " ; " <constraint>
<six_constraints> ::= <five_constraints> " ; " <constraint>
<five_constraints> ::= <four_constraints> " ; " <constraint>
<four_constraints> ::= <three_constraints> " ; " <constraint>
<three_constraints> ::= <two_constraints> " ; " <constraint>
<two_constraints> ::= <constraint> " ; " <constraint>


<constraint> ::= <unit_constraint> | <unit_constraint> " || " <constraint>

<unit_constraint> ::= <date_var> <cmp_op> <expr> | "(" <bool_var_expr> ") -> (" <expr> <cmp_op> <expr> ")" | <int_var> <cmp_op> <int_var_expr>

<expr> ::= <date_var_expr> | <date_expr>

<date_var_expr> ::= <date_var> | "(" <date_var_expr> <add_sub_op> <period_expr> ")"

# Cannot have recursive date_expr since we do not have add_sub operations on date.
<date_expr> ::= <date_ctor> | "(" <date_ctor> <add_sub_op> <period_expr> ")"

<period_expr> ::= <period_ctor> | "(" <period_ctor> <add_sub_op> <period_expr> ")" | "(" <period_expr> " * " <digit> ")"

<date_ctor> ::= "Date(" <date_year> ", " <date_month> ", " <date_day> ")"
<period_ctor> ::= "Period(" <period_year> ", " <period_month> ", " <period_day> ")"

<cmp_op> ::= " == " | " != " | " < " | " <= " | " > " | " >= "
<add_sub_op> ::= " + " | " - "

<date_var> ::= "D"<digit>

<date_year> ::= "19"<digit><digit> | "20"<digit><digit> | "21"<digit><digit>
<date_month> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12"
<date_day> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12" | "13" | "14" | "15" | "16" | "17" | "18" | "19" | "20" | "21" | "22" | "23" | "24" | "25" | "26" | "27" | "28" | "29" | "30" | "31"

# Note: Set to small numbers on purpose
<period_year> ::= <digit>
<period_month> ::= <digit>
<period_day> ::= <digit>

<bool_var_expr> ::= <bool_var> <bool_cmp_op> <bool_val>
<bool_var> ::= "B"<digit>
<bool_cmp_op> ::= " == " | " != "
<bool_val> ::= "True" | "False"

<int_var_expr> ::= <int_var> | <date_year> | <date_month> | <date_day> | "(" <int_var> <arith_op> <int_var_expr> ")"
<int_var> ::= "I"<digit> | <date_var> "." <date_field>
<date_field> ::= "year" | "month" | "day"
<arith_op> ::= " + " | " - " | " * " | " // " | " % "

##################################################
# Post-processing
##################################################

where is_valid_date_ctor(str(<date_ctor>)) 

def is_valid_date_ctor(date_ctor: str) -> bool:
    """Return True iff `date_ctor` represents a valid date between
    1900-03-01 and 2100-02-28 inclusive.

    Examples of valid:
      Date(1900, 3, 1)
      Date(2000, 2, 29)    # leap year
      Date(2099, 12, 31)

    Examples of invalid:
      Date(1900, 2, 28)    # before lower bound
      Date(2100, 2, 28)    # valid day but out of range (exclusive upper)
      Date(2023, 2, 29)    # invalid day
    """

    # Match Date(YYYY, M, D)
    m = re.fullmatch(r"Date\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2})\)", date_ctor.strip())
    if not m:
        return False

    year, month, day = map(int, m.groups())

    # Ensure year is within representable grammar bounds
    if not (1900 <= year <= 2100):
        return False

    try:
        d = datetime.date(year, month, day)
    except ValueError:
        # invalid month/day combination
        return False

    # Range check: 1900-03-01 ≤ d ≤ 2100-02-28
    lower = datetime.date(1900, 3, 1)
    upper = datetime.date(2100, 2, 28)
    return lower <= d <= upper
