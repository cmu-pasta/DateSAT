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
# this file as `python dataset/utils/test.py`.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datesmt.api import DateSMTBuilder
from datesmt.constraint_parser import ConstraintParser
from datesmt.core import Date, Period

# Paste a single JSON constraint object here (one from *_constraints*.jsonl)
CONSTRAINT_JSON = r"""
{
    "declarations": [
      "D1: date",
      "D2: date",
      "D3: date",
      "D4: date",
      "D5: date",
      "D6: date",
      "D7: date",
      "D8: date",
      "D9: date"
    ],
    "constraints": [
      "D1 == D9",
      "D2 == Date(2028, 9, 25)",
      "D1 <= (D6 - (Period(9, 7, 7) + (Period(6, 0, 0) + Period(9, 5, 5)))) || D4 < (D1 + (Period(5, 3, 9) - Period(0, 7, 9))) || D7 >= (Date(2059, 9, 13) - Period(7, 0, 4)) || D9 != (Date(2045, 12, 20) + ((Period(9, 9, 7) - (Period(0, 6, 0) + (Period(6, 0, 9) * 6))) * 6))",
      "D6 < D3 || D5 > D4 || D2 >= D6",
      "D2 != D7",
      "D1 != (D6 + (Period(7, 0, 2) - (Period(4, 2, 5) + Period(6, 7, 5))))",
      "D9 > ((D4 - (Period(1, 5, 0) + Period(2, 3, 8))) - Period(4, 4, 2)) || D8 > D6",
      "D8 != ((D6 - (Period(5, 7, 4) * 5)) + ((Period(2, 0, 9) - (Period(0, 0, 5) + (Period(1, 3, 3) + Period(7, 8, 7)))) * 1))",
      "D8 <= D2 || D1 == ((D8 + Period(4, 0, 8)) + Period(8, 3, 2))"
    ]
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

    # The generated code creates a `builder` variable
    builder = exec_globals.get("builder")
    if builder is None:
        raise RuntimeError("Generated code did not create a builder")

    # 4) Solve and print results
    builder.solve()  # DateSMTBuilder.solve() already prints SAT/UNSAT and dates


if __name__ == "__main__":
    main()
