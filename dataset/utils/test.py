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
    "id": "grammar-41",
    "declarations": [
      "B: date",
      "E: date",
      "W: date",
      "by: int",
      "bm: int",
      "ey: int",
      "em: int",
      "mraw: int",
      "mb: int",
      "dlt: bool",
      "B_bounds: bool",
      "B_index: bool"
    ],
    "constraints": [
      "W   == B + Period(0, 18, 0)",
      "by  == B.year",
      "bm  == B.month",
      "ey  == E.year",
      "em  == E.month",
      "mraw == (ey - by) * 12 + (em - bm)",
      "dlt == (E.day < B.day)",
      "(dlt  -> (mb == mraw - 1))",
      "(!dlt -> (mb == mraw))",
      "B_bounds == ((E >= B) && (E < W))",
      "B_index  == ((E >= B) && ((mb / 18) == 0))",
      "B_bounds != B_index"
    ],
    "size": 11
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
        return DateSMTBuilder(approach="naive", implementation="bitvector")

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
