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
from datesmt.core import Date, Period
from datesmt.constraint_parser import ConstraintParser


# Paste a single JSON constraint object here (one from *_constraints*.jsonl)
CONSTRAINT_JSON = r"""
{
    "id": "grammar-17",
    "declarations": [
      "B0: bool",
      "B4: bool",
      "B7: bool",
      "B9: bool",
      "D1: date",
      "D2: date",
      "D3: date",
      "D4: date",
      "D5: date",
      "D7: date",
      "D8: date",
      "D9: date",
      "I3: int",
      "I6: int"
    ],
    "constraints": [
      "(B0 == True) -> (D1 == D1) || D8 <= D5",
      "I3 == (I6 - 1) || (B7 == False) -> (Date(1926, 6, 11) >= (Date(2044, 3, 16) - (Period(0, 0, 8) * 5))) || D4 > D5 || (B9 != True) -> ((Date(1903, 11, 12) - (Period(9, 1, 4) * 9)) == D7) || D8 <= Date(2068, 5, 4)",
      "D2 > (D8 - ((Period(5, 1, 5) - ((Period(2, 2, 8) * 2) * 4)) * 1)) || (B4 == True) -> (D3 < (D9 + (((Period(1, 3, 4) - (Period(6, 6, 1) + Period(1, 6, 4))) * 8) * 7)))",
      "D3.year == (D2.month - 12)",
      "(B0 == True) -> ((Date(2009, 4, 19) - (Period(8, 9, 1) + (((Period(5, 0, 0) - (((Period(3, 7, 2) - (Period(0, 9, 0) - (((Period(0, 1, 4) * 0) * 5) * 5))) * 4) * 6)) * 4) * 8))) > D7)",
      "D4 > D9",
      "D5.day > 2024"
    ],
    "size": 7
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
