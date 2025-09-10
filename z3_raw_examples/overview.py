# Date(2023,10,01) <= x and (y + Period(0,1,0)) < Date(2024,1,15) and (x + Period(0,0,30)) = y
# Satisfiable: x = 2023.10.18, y = 2023.11.17

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from z3 import *

# Epoch base date
EPOCH = date(2000, 3, 1)


# Convert calendar date to Z3 integer (days since EPOCH)
def date_to_days(year, month, day):
    return (date(year, month, day) - EPOCH).days


# Convert Z3 integer to calendar date
def days_to_date(days):
    return EPOCH + timedelta(days=days)


# Compute y + 1 month using real calendar rules
def add_one_month(d: date):
    return d + relativedelta(months=1)


# Problem constants
d_2023_10_01 = date_to_days(2023, 10, 1)
d_2024_01_15 = date_to_days(2024, 1, 15)

# Declare symbolic variables
x = Int('x')
y = Int('y')

# Create solver
s = Solver()

# Constraint 1: x >= 2023.10.01
s.add(x >= d_2023_10_01)

# Constraint 2: x + 30 = y (30-day addition)
s.add(x + 30 == y)

# Constraint 3: y + 1 month < 2024.01.15
# Enumerate all y candidates from the interval and check the 1-month-ahead constraint
valid_y_vals = []
start_date = days_to_date(d_2023_10_01 + 30)  # earliest y from x + 30
end_date = days_to_date(d_2024_01_15 - 1)  # strict less than

# Check every candidate y in the interval, filter based on calendar month logic
for day_offset in range((end_date - start_date).days + 1):
    y_candidate_date = start_date + timedelta(days=day_offset)
    y_plus_1m = add_one_month(y_candidate_date)
    print(f"Checking y = {y_candidate_date} → y + 1 month = {y_plus_1m}")
    if y_plus_1m < days_to_date(d_2024_01_15):
        valid_y_vals.append(
            date_to_days(
                y_candidate_date.year, y_candidate_date.month, y_candidate_date.day
            )
        )

# Constraint 3: y must be one of these valid values
s.add(Or([y == v for v in valid_y_vals]))

# Solve
if s.check() == sat:
    m = s.model()
    x_val = m[x].as_long()
    y_val = m[y].as_long()
    x_date = days_to_date(x_val)
    y_date = days_to_date(y_val)
    print("SAT")
    print(f"x = {x_val} (x_date: {x_date})")
    print(f"y = {y_val} (y_date: {y_date})")
else:
    print("UNSAT")
