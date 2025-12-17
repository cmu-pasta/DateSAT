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
    "id": "grammar-sat-1",
    "declarations": [
      "B0: bool",
      "B2: bool",
      "B5: bool",
      "B6: bool",
      "D0: date",
      "D2: date",
      "D3: date",
      "D5: date",
      "D6: date",
      "D7: date",
      "D8: date",
      "D9: date",
      "I4: int",
      "I6: int",
      "I7: int"
    ],
    "constraints": [
      "I4 < 2165 || (B0 != True) -> (D5 >= Date(2074, 11, 10)) || (B0 != False) -> ((((D7 + (Period(0, 0, 6) + ((Period(1, 6, 4) - Period(1, 2, 6)) * 5))) - (Period(5, 4, 8) + (Period(4, 0, 3) * 4))) + (Period(1, 4, 8) * 4)) >= (Date(1968, 4, 2) + (Period(7, 0, 5) - ((Period(8, 1, 6) - Period(6, 2, 0)) * 4)))) || D5 == D7",
      "D8 != D8 || D9 < Date(1935, 11, 7)",
      "(B5 == False) -> (D0 >= D9)",
      "D3 < ((D5 - (Period(8, 9, 8) + (Period(7, 6, 2) * 0))) - Period(4, 2, 5)) || D7 != D3",
      "(B2 != False) -> (Date(2032, 9, 29) == (D2 - (Period(7, 0, 0) + ((Period(1, 4, 7) + Period(4, 6, 8)) * 1)))) || I6 != D6.day",
      "D9.month != I7 || (B6 == True) -> (D5 != D8)"
    ],
    "size": 6,
    "execution_time": 53.237571001052856
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
        return DateSMTBuilder(approach="naive", implementation="int")

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
