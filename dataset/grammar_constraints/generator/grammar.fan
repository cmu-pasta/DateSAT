##################################################
# Library imports
##################################################
import re
import datetime


##################################################
# Generator grammar
##################################################

<start> ::= <constraint_list>
<constraint_list> ::= <constraint> | <constraint> " ; " <constraint_list>

# NOTE: Pinned LHS to var to ensure that is there always a var in the constraint and its not something like: (Date(1956,7,8)+((((Period(0,6,54419)*6)-(Period(3,90,9)*21))-Period(8,728,7))-Period(87,55,2)))<Date(1907,9,14). 
# I do not see if <expr> <cmp_op> <expr> would generate something new.
<constraint> ::= <var> <cmp_op> <expr>

# Do not need a hybrid expr with both dates and vars since that is not allowed
<expr> ::= <var_expr> | <date_expr>

# We cannot have  "(" <var_expr> <add_sub_op> <var_expr> ")" since it could add two date vars which is not allowed
<var_expr> ::= <var> | "(" <var_expr> <add_sub_op> <period_expr> ")"

# Cannot have recursive date_expr since we do not have add_sub operations on date.
<date_expr> ::= <date_ctor> | "(" <date_ctor> <add_sub_op> <period_expr> ")"

<period_expr> ::= <period_ctor> | "(" <period_expr> <add_sub_op> <period_expr> ")" | "(" <period_expr> "*" <digit>{1,2} ")"

<date_ctor> ::= "Date(" <date_year> "," <date_month> "," <date_day> ")"
<period_ctor> ::= "Period(" <period_year> "," <period_month> "," <period_day> ")"

<cmp_op> ::= "==" | "!=" | "<" | "<=" | ">" | ">="
<add_sub_op> ::= "+" | "-"

# TODO: Should we only keep these many vars?
<var> ::= "x" | "y" | "z"

<date_year> ::= "19"<digit><digit> | "20"<digit><digit> | "21"<digit><digit>
<date_month> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12"
<date_day> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12" | "13" | "14" | "15" | "16" | "17" | "18" | "19" | "20" | "21" | "22" | "23" | "24" | "25" | "26" | "27" | "28" | "29" | "30" | "31"

<period_year> ::= <digit>
<period_month> ::= <digit>{1,2}
<period_day> ::= <digit>{1,3}


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
