"""
Quick DateSMT runner for a single JSON constraint object.

Usage:
1. Copy a JSON object from constraints JSONL (one line), e.g.:

   {"description": "...", "constraints": [...], "id": "1", ...}

2. Paste it into CONSTRAINT_JSON below (between the triple quotes).
3. Run:

   cd /Users/angelcui/Documents/GitHub/Date-SMT
   python3 dataset/test.py

It will:
- Parse the JSON
- Use datesmt.constraint_parser to turn the constraints into executable code
- Build a DateSMT solver
- Solve and print the model to the terminal
"""

import json
import sys
from pathlib import Path

# Ensure repository root is on sys.path so we can import `datesmt` when running
# this file as `python dataset/test.py`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datesmt.api import DateSMTBuilder
from datesmt.constraint_parser import ConstraintParser
from datesmt.core import Date, Period

# Paste a single JSON constraint object here (one from *_constraints*.jsonl)
CONSTRAINT_JSON = r"""
{
    "id": "grammar-10",
    "declarations": [
      "B0: bool",
      "B1: bool",
      "B6: bool",
      "B8: bool",
      "D0: date",
      "D1: date",
      "D2: date",
      "D3: date",
      "D4: date",
      "D5: date",
      "D8: date",
      "D9: date",
      "I1: int",
      "I2: int",
      "I4: int",
      "I5: int",
      "I6: int",
      "I8: int"
    ],
    "constraints": [
      "(B6 != True) -> ((D9 + Period(3, 3, 9)) < Date(2064, 3, 18)) || D0 >= Date(1912, 4, 11) || I2 >= 2021",
      "(B0 != True) -> (D5 <= (D2 - Period(9, 6, 4)))",
      "I6 != 8 || D2 != (Date(2087, 12, 18) + ((Period(9, 1, 2) * 2) * 9)) || D0 <= (D2 - Period(5, 3, 0)) || D8 < (((D1 - (Period(9, 5, 0) - Period(0, 6, 5))) - (Period(0, 3, 2) - (Period(9, 2, 1) + (Period(0, 5, 6) + ((Period(9, 7, 4) + Period(0, 4, 3)) * 5))))) + ((((Period(4, 8, 9) + Period(5, 9, 4)) * 2) * 1) * 5)) || D5.year < 6 || D9.month <= (D1.year + (I1 * 2033)) || (B1 == False) -> (D4 == Date(2064, 10, 3)) || (B6 == True) -> (D9 > (Date(1930, 9, 27) + Period(8, 9, 8)))",
      "D8 < Date(1919, 4, 5)",
      "I4 == 23",
      "I1 <= (I8 - 1) || D4.year < I5",
      "D3.month != (I1 - 2038)",
      "(B0 == True) -> (D5 == D0) || (B8 != True) -> (D2 == Date(2059, 10, 23))",
      "D3 != (Date(2069, 6, 8) + (Period(8, 3, 2) * 8))"
    ],
    "size": 9
  }
"""


def main():
    # 1) Parse the pasted JSON
    constraint_data = json.loads(CONSTRAINT_JSON)

    # 2) Use the DateSMT constraint parser to turn it into Python code
    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)

    print("=== Generated constraint code ===")
    print(constraint_code)
    print("=================================\n")

    # 3) Execute the generated code with a DateSMTBuilder factory
    def create_builder():
        # You can change approach/implementation if you want
        return DateSMTBuilder(approach="alpha_beta", implementation="bitvector")

    exec_globals = {
        "Date": Date,
        "Period": Period,
        "DateSMTBuilder": create_builder,
    }

    exec(constraint_code, exec_globals)

    # The generated code sets `result = builder`
    builder = exec_globals.get("result")
    if builder is None:
        raise RuntimeError("Generated code did not create a builder named 'result'")

    # 4) Solve and print results
    builder.solve()  # DateSMTBuilder.solve() already prints SAT/UNSAT and dates


if __name__ == "__main__":
    main()
