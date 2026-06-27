import json
import sys
import time
from pathlib import Path

# Ensure repository root is on sys.path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datesat.api import DateSATBuilder
from datesat.constraint_parser import ConstraintParser
from datesat.core import Date, Period

CONSTRAINT_JSON = r"""
{
    "declarations": [
      "base: date",
      "event: date",
      "window_end: date",
      "elapsed_m: int",
      "elapsed_m_adj: int",
      "result_1: bool",
      "result_2: bool"
    ],
    "constraints": [
      "base <= event",
      "elapsed_m == (event.year - base.year) * 12 + (event.month - base.month)",
      "((event.day < base.day) -> (elapsed_m_adj == elapsed_m - 1))",
      "((event.day >= base.day) -> (elapsed_m_adj == elapsed_m))",
      "result_1 == (elapsed_m_adj < 18)",
      "window_end == base + Period(0, 18, 0)",
      "result_2 == (event < window_end)",
      "result_1 != result_2"
    ]
  }
"""


def main():
    print("=" * 60)
    print("DateSAT Constraint Runner")
    print("=" * 60)
    print()

    # 1) Parse the JSON constraint object
    constraint_data = json.loads(CONSTRAINT_JSON)

    print("Input Constraints:")
    print("-" * 40)
    for decl in constraint_data.get("declarations", []):
        print(f"  declare: {decl}")
    for constraint in constraint_data.get("constraints", []):
        print(f"  constraint: {constraint}")
    print()

    # 2) Use ConstraintParser to generate executable code
    parser = ConstraintParser()
    constraint_code = parser.parse_constraint_data(constraint_data)

    print("Generated Code:")
    print("-" * 40)
    print(constraint_code)
    print()

    # 3) Execute the generated code with DateSATBuilder
    def create_builder():
        # Options: approach="simple"|"epoch_days"|"alpha_beta"|"hybrid"
        #          implementation="int"|"bv"
        return DateSATBuilder(approach="simple", implementation="int")

    exec_globals = {
        "Date": Date,
        "Period": Period,
        "DateSATBuilder": create_builder,
    }

    exec(constraint_code, exec_globals)

    # Get the builder created by the generated code
    builder = exec_globals.get("builder")
    if builder is None:
        raise RuntimeError("Generated code did not create a builder")

    # 4) Solve and display results
    print("Solving...")
    print("-" * 40)
    start_time = time.time()
    builder.solve()  # Prints SAT/UNSAT and model values
    elapsed_time = time.time() - start_time
    print()
    print(f"Time taken: {elapsed_time:.4f} seconds")


if __name__ == "__main__":
    main()
