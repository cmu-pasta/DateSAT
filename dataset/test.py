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
    "id": "grammar-41",
    "declarations": [
      "B0: bool",
      "D0: date",
      "D1: date",
      "D2: date",
      "D4: date",
      "D6: date",
      "D7: date",
      "D8: date",
      "D9: date",
      "I0: int",
      "I3: int",
      "I4: int",
      "I6: int",
      "I8: int",
      "I9: int"
    ],
    "constraints": [
      "D9.month > (I3 % (D8.month / 11))",
      "I9 == 22 || D6 != Date(2003, 11, 30)",
      "(B0 == False) -> ((D8 - Period(6, 7, 4)) == ((D1 - (Period(4, 7, 6) + ((Period(2, 9, 7) * 9) * 2))) - (Period(9, 2, 4) + ((Period(0, 4, 1) - ((Period(0, 2, 9) * 6) * 6)) * 7))))",
      "I6 >= 2061 || D4 >= D7",
      "I9 >= 8 || I0 > (I4 / (D6.day * 2120)) || D9.month >= (D7.year - 2182) || D1 > (Date(2056, 8, 3) - Period(1, 4, 3)) || D6 == Date(1954, 4, 18) || D8 != (D2 + Period(8, 2, 2))",
      "D1 <= (Date(2093, 7, 3) + Period(8, 8, 1)) || D6.year < 9 || D1.year >= 1965 || D0 >= ((D8 + (Period(3, 9, 4) * 1)) + (Period(2, 9, 2) - (Period(4, 0, 0) * 8))) || (B0 != True) -> ((D7 - ((((Period(8, 7, 8) * 0) * 7) * 2) * 2)) > D0) || D7.day > D1.month || D7 != ((((D9 + Period(0, 5, 5)) - (Period(9, 2, 5) * 9)) + Period(1, 2, 5)) + (Period(7, 9, 8) * 8)) || I8 <= D9.month"
    ],
    "size": 6
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
        return DateSMTBuilder(approach="naive", implementation="int", timeout_ms=6000)

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
