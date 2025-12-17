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
    "id": "grammar-67",
    "declarations": [
      "B1: bool",
      "B3: bool",
      "B8: bool",
      "D0: date",
      "D1: date",
      "D2: date",
      "D3: date",
      "D4: date",
      "D5: date",
      "D6: date",
      "D8: date",
      "D9: date",
      "I2: int",
      "I7: int",
      "I8: int"
    ],
    "constraints": [
      "D2 <= Date(1931, 9, 26)",
      "D3 > D3",
      "(B1 != False) -> ((Date(2024, 4, 26) + ((Period(4, 0, 1) - Period(0, 7, 2)) * 7)) <= (Date(2092, 12, 22) - (Period(4, 8, 4) + (Period(1, 3, 7) * 0)))) || I7 > 10",
      "I8 >= 19 || D1.year > 5",
      "D5 > ((D5 - Period(2, 0, 1)) - Period(0, 6, 1)) || D1.month == D4.month",
      "I2 == (D5.day - 16)",
      "D9 == D8 || (B8 == True) -> (Date(2073, 5, 10) != ((D4 - Period(7, 6, 7)) - Period(6, 4, 8))) || D6 >= (D0 - ((Period(3, 0, 3) + (Period(0, 2, 2) - (Period(7, 9, 6) * 0))) * 3))",
      "(B3 == True) -> ((D4 + (Period(4, 4, 2) - (Period(0, 8, 9) - Period(8, 3, 3)))) < D8) || D5.year < 3"
    ],
    "size": 8
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
