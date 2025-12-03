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
  "description": "Temporal constraints for tax table adjustments and marriage penalty phaseout",
  "constraints": [
    "prescription_deadline >= Date(1993, 12, 15)",
    "prescription_deadline <= Date(2099, 12, 15)",
    "taxable_year_start >= Date(1901, 1, 1)",
    "taxable_year_start <= Date(2099, 1, 1)",
    "taxable_year_end >= taxable_year_start",
    "taxable_year_end <= taxable_year_start + Period(1, 0, 0) - Period(0, 0, 1)",
    "succeeding_year_start >= taxable_year_start + Period(1, 0, 0)",
    "succeeding_year_start <= taxable_year_start + Period(2, 0, 0)",
    "cpi_measurement_period_end >= Date(1900, 8, 31)",
    "cpi_measurement_period_end <= Date(2099, 8, 31)",
    "ccpi_publication_date >= cpi_measurement_period_end",
    "ccpi_publication_date < prescription_deadline",
    "marriage_penalty_cutoff_date == Date(2003, 12, 31)",
    [
      "taxable_year_start > marriage_penalty_cutoff_date",
      "marriage_penalty_applies == false"
    ],
    [
      "taxable_year_start <= marriage_penalty_cutoff_date",
      "marriage_penalty_applies == true"
    ]
  ],
  "provenance": {
    "hierarchy": {
      "title": 26,
      "subtitle": null,
      "chapter": null,
      "subchapter": null,
      "part": null,
      "subpart": null,
      "section": null
    },
    "subsection_path": "(s1)(f)",
    "identifier": "/us/usc/t26/s1/f",
    "original_text": "(f) Phaseout of marriage penalty in 15-percent bracket; adjustments in tax tables so that inflation will not result in tax increases (1) In general Not later than December 15 of 1993, and each subsequent calendar year, the Secretary shall prescribe tables which shall apply in lieu of the tables contained in subsections (a), (b), (c), (d), and (e) with respect to taxable years beginning in the succeeding calendar year. (2) Method of prescribing tables The table which under paragraph (1) is to apply in lieu of the table contained in subsection (a), (b), (c), (d), or (e), as the case may be, with respect to taxable years beginning in any calendar year shall be prescribed— (A) except as provided in paragraph (8), by increasing the minimum and maximum dollar amounts for each bracket for which a tax is imposed under such table by the cost-of-living adjustment for such calendar year, determined— (i) except as provided in clause (ii), by substituting “1992” for “2016” in paragraph (3)(A)(ii), and (ii) in the case of adjustments to the dollar amounts at which the 36 percent rate bracket begins or at which the 39.6 percent rate bracket begins, by substituting “1993” for “2016” in paragraph (3)(A)(ii), (B) by not changing the rate applicable to any rate bracket as adjusted under subparagraph (A), and (C) by adjusting the amounts setting forth the tax to the extent necessary to reflect the adjustments in the rate brackets. (3) Cost-of-living adjustment For purposes of this subsection— (A) In general The cost-of-living adjustment for any calendar year is the percentage (if any) by which— (i) the C-CPI-U for the preceding calendar year, exceeds (ii) the CPI for calendar year 2016, multiplied by the amount determined under subparagraph (B). (B) Amount determined The amount determined under this clause is the amount obtained by dividing— (i) the C-CPI-U for calendar year 2016, by (ii) the CPI for calendar year 2016. (C) Special rule for adjustments with a base year after 2016 For purposes of any provision of this title which provides for the substitution of a year after 2016 for “2016” in subparagraph (A)(ii), subparagraph (A) shall be applied by substituting “the C-CPI-U for calendar year 2016” for “the CPI for calendar year 2016” and all that follows in clause (ii) thereof. (4) CPI for any calendar year For purposes of paragraph (3), the CPI for any calendar year is the average of the Consumer Price Index as of the close of the 12-month period ending on August 31 of such calendar year. (5) Consumer Price Index For purposes of paragraph (4), the term “Consumer Price Index” means the last Consumer Price Index for all-urban consumers published by the Department of Labor. For purposes of the preceding sentence, the revision of the Consumer Price Index which is most consistent with the Consumer Price Index for calendar year 1986 shall be used. (6) C-CPI-U For purposes of this subsection— (A) In general The term “C-CPI-U” means the Chained Consumer Price Index for All Urban Consumers (as published by the Bureau of Labor Statistics of the Department of Labor). The values of the Chained Consumer Price Index for All Urban Consumers taken into account for purposes of determining the cost-of-living adjustment for any calendar year under this subsection shall be the latest values so published as of the date on which such Bureau publishes the initial value of the Chained Consumer Price Index for All Urban Consumers for the month of August for the preceding calendar year. (B) Determination for calendar year The C-CPI-U for any calendar year is the average of the C-CPI-U as of the close of the 12-month period ending on August 31 of such calendar year. (7) Rounding (A) In general If any increase determined under paragraph (2)(A), section 63(c)(4), section 68(b)(2) 1 or section 151(d)(4) is not a multiple of $50, such increase shall be rounded to the next lowest multiple of $50. (B) Table for married individuals filing separately In the case of a married individual filing a separate return, subparagraph (A) (other than with respect to sections 63(c)(4) and 151(d)(4)(A)) shall be applied by substituting “$25” for “$50” each place it appears. (8) Elimination of marriage penalty in 15-percent bracket With respect to taxable years beginning after December 31, 2003 , in prescribing the tables under paragraph (1)— (A) the maximum taxable income in the 15-percent rate bracket in the table contained in subsection (a) (and the minimum taxable income in the next higher taxable income bracket in such table) shall be 200 percent of the maximum taxable income in the 15-percent rate bracket in the table contained in subsection (c) (after any other adjustment under this subsection), and (B) the comparable taxable income amounts in the table contained in subsection (d) shall be ½ of the amounts determined under subparagraph (A).",
    "heading": "Tax imposed"
  },
  "id": "1",
  "parsed_id": "6"
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
        return DateSMTBuilder(approach="epoch_days", implementation="int")

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
