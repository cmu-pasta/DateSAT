"""
Two-step LLM-based extraction of date/time constraints from legal text (Title 26).

This script implements a small two-step LLM pipeline:
1. Analysis step: identify entities and temporal references in the legal text.
2. Generation step: generate DateSMT constraints directly from the analysis + text.

Compared to the single-call llm_extractor.py, this version uses two
consecutive LLM calls per record with shared conversation history to
potentially improve reasoning, but it is not a full tool-using 2 step llm pipeline.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataset.llm import LLMPipeline
from datesmt.constraint_parser import ConstraintParser
from format_jsonl import format_as_pretty_jsonl


def _validate_constraints_with_parser(constraints: List) -> Tuple[bool, Optional[str]]:
    """
    Validate constraints by actually parsing them with the ConstraintParser.
    
    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    if not constraints:
        return True, None
    
    try:
        parser = ConstraintParser()
        # generate_builder_code validates and parses all constraints
        parser.generate_builder_code(constraints)
        return True, None
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Parser error: {str(e)}"


def _handle_validation_error(
    feedback_msg: str,
    feedback_type: str,
    record_id: str,
    attempt: int,
    max_retries: int,
    log_file,
    log_entry: Dict,
    error_details: Optional[Dict] = None,
) -> Tuple[str, bool]:
    """
    Handle a validation error during constraint extraction.
    
    Returns:
        Tuple of (feedback_message, should_return_none).
    """
    if log_file:
        log_entry["llm_calls"].append({
            "step": "generation",
            "attempt": attempt,
            "feedback_type": feedback_type,
            "feedback": feedback_msg,
        })
    
    if attempt == max_retries:
        if log_file:
            log_entry["error"] = feedback_type
            if error_details:
                log_entry.update(error_details)
            log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            log_file.flush()
        return feedback_msg, True
    
    return feedback_msg, False


ANALYSIS_PROMPT = """You are analyzing legal text from Title 26 (Internal Revenue Code) to identify temporal entities and events.

Your task is to identify:
1. What entities/events are mentioned (e.g., marriage, filing, tax year, payment, assessment, etc.)
2. What explicit temporal (date/period) references exist (dates, periods, deadlines, etc.)
3. What implicit temporal (date/period) relationships might be needed

Output a JSON object with:
{
  "entities_mentioned": ["entity1", "entity2", ...],
  "explicit_temporal_refs": ["ref1", "ref2", ...],
  "implicit_relationships": ["relationship1", "relationship2", ...],
  "reasoning": "Brief explanation of what you found"
}

Be precise - only list entities/events actually mentioned in the text."""

GENERATION_PROMPT = """You are an expert in temporal reasoning, specializing in converting legal clauses from the U.S. Internal Revenue Code (Title 26) into precise DateSMT constraints.

Your task:  
Given a passage of legal text, extract all explicit and logically required date/period constraints and express them in the DateSMT DSL.  
You must output ONLY valid JSON following the schema below.

────────────────────────────────────────────────────────
I. DSL TYPES & DECLARATIONS
────────────────────────────────────────────────────────
Variable types (can be declared as symbolic):
- date: symbolic date variable (e.g., "filing_date: date")
- int: symbolic integer variable (e.g., "tax_year: int")
- bool: symbolic boolean variable (e.g., "is_married: bool")

Constructors (concrete values only, NOT variable types):
- Date(year, month, day): concrete date OR with int variables (e.g., Date(2020, 1, 15) or Date(year_val, 1, 15))
- Period(years, months, days): concrete period ONLY (e.g., Period(3, 0, 0)) — NO symbolic period variables

Rules:
- All variables must be declared before use, except integers appearing only as arguments to Date().
- Declarations must be SEPARATE constraint strings, NOT inside other constraints.
  WRONG: "(A) -> (x: bool)"
  RIGHT: "x: bool", "(A) -> (x == True)"
- Period() ONLY accepts concrete integers — you CANNOT create symbolic period variables
- Use parentheses () to group expressions and avoid ambiguity:
  WRONG: "a + b * c" (ambiguous)
  RIGHT: "(a + b) * c" or "a + (b * c)"
  WRONG: "A -> B -> C" (chained, invalid)
  RIGHT: "(A) -> ((B) -> (C))" (nested, valid)

────────────────────────────────────────────────────────
II. ALLOWED OPERATIONS
────────────────────────────────────────────────────────
Date arithmetic:
- Date ± Period → Date  
- Date ▷◁ Date (▷◁ ∈ {==, !=, <, <=, >, >=})

Period:
- Period ± Period → Period  
- Period * Int → Period  

Integers:
- Int ± Int → Int  
- Int * Int → Int  
- Accessors: k.year, k.month, k.day → int

Booleans:
- Bool == Bool  
- Use True/False literals  
- Implication: (A) -> (B)
- Nested implication for "if A and B then C": (A) -> ((B) -> (C))

────────────────────────────────────────────────────────
III. FORBIDDEN EXPRESSIONS
────────────────────────────────────────────────────────
- Period ▷◁ Period  (compare dates after applying periods instead)
- Boolean arithmetic (bool + int, bool * bool, etc.)
- And(), Or(), Not() functions — use CNF clauses and implications instead
- && and || operators — use nested implications or CNF format instead
- Chained implications like (A) -> (B) -> (C) — use nested: (A) -> ((B) -> (C))
- Dates outside 1900-03-01 to 2100-02-28
- Undeclared variables (except int args to Date())

────────────────────────────────────────────────────────
IV. CNF FORMAT RULES (CRITICAL)
────────────────────────────────────────────────────────
Output is a JSON object:
{
  "description": "...",
  "constraints": [...]
}

Where:
- Top-level array = AND
- A nested array = OR clause
- Variable declarations appear as constraints

Example:
["k: date", "k >= Date(2020,1,1)"]  
or  
[ ["A <= B + Period(3,0,0)", "A <= C + Period(2,0,0)"], "B >= Date(2020,1,1)" ]

────────────────────────────────────────────────────────
V. COMMON-KNOWLEDGE INFERENCE RULES
────────────────────────────────────────────────────────
You may actively infer and add **implicit** temporal constraints, but ONLY when:

1. The entity is explicitly mentioned  
   Examples: “taxable year”, “married individual”, “return filed”, “claim”, “spouse”

2. The temporal relationship is REQUIRED for the statute to make sense  
   Examples:
   - Filing must occur after the taxable year ends  
   - Joint filing requires marriage to occur on or before filing_date  
   - Taxable year has boundaries:
        taxable_year_end >= taxable_year_start  
        taxable_year_end <= taxable_year_start + Period(1,0,0)

3. The inference is minimal and legally necessary  
   Do NOT infer unrelated facts (e.g., do not introduce birthdays unless spouse/individual is mentioned).

4. NEVER introduce new actors not present in the text.  
   (No marriage_date if the text doesn’t mention marriage.)

────────────────────────────────────────────────────────
VI. EXTRACTION LOGIC
────────────────────────────────────────────────────────
For each legal passage:
1. Identify explicit dates, deadlines, periods, temporal phrases.
2. Introduce variables with clear, context-specific names.
3. Encode all explicit temporal relations.
4. Add only those implicit constraints required for legal coherence.
5. Convert conditional language to implication.
6. Convert alternatives to OR clauses.
7. Use property accessors when needed (k.year == 2020).

────────────────────────────────────────────────────────
VII. OUTPUT REQUIREMENTS (STRICT)
────────────────────────────────────────────────────────
You MUST output **ONLY ONE** of the following:

1. A JSON object with fields:
   - "description": short summary  
   - "constraints": array of constraints or CNF clauses  

2. The literal value:
   null  
   (Only when the passage contains *no* date, time, period, or temporal semantics.)

No explanations.  
No reasoning.  
No comments.  
No text before or after the JSON.

────────────────────────────────────────────────────────
VIII. EXAMPLES (for reference)
────────────────────────────────────────────────────────

Example 1: Deadline with Period arithmetic
Legal Text: "A claim for credit or refund must be filed within 3 years from the time the return was filed."
Output:
{
  "description": "Claim must be filed within 3 years of return filing",
  "constraints": [
    "claim_date: date",
    "return_filing_date: date",
    "claim_date >= return_filing_date",
    "claim_date <= return_filing_date + Period(3, 0, 0)"
  ]
}

Example 2: Property access + symbolic Date constructor
Legal Text: "The estimated tax payment is due on the 15th day of the 4th month of the following taxable year."
Output:
{
  "description": "Payment due on April 15 of the year after taxable year ends",
  "constraints": [
    "taxable_year_end: date",
    "payment_due: date",
    "next_year: int",
    "next_year == taxable_year_end.year + 1",
    "payment_due == Date(next_year, 4, 15)"
  ]
}

Example 3: Boolean flag with implication
Legal Text: "If the taxpayer elects to apply the credit, the election must be made before the due date of the return."
Output:
{
  "description": "If credit election is made, it must occur before return due date",
  "constraints": [
    "credit_elected: bool",
    "election_date: date",
    "return_due_date: date",
    "(credit_elected == True) -> (election_date <= return_due_date)"
  ]
}

Example 4: OR clause for alternatives
Legal Text: "The period of limitation shall be 3 years after the return was filed, or 2 years after the tax was paid, whichever is later."
Output:
{
  "description": "Limitation period ends at the later of 3 years after filing or 2 years after payment",
  "constraints": [
    "filing_date: date",
    "payment_date: date",
    "limitation_end: date",
    "limitation_end >= filing_date + Period(3, 0, 0)",
    "limitation_end >= payment_date + Period(2, 0, 0)",
    [
      "limitation_end == filing_date + Period(3, 0, 0)",
      "limitation_end == payment_date + Period(2, 0, 0)"
    ]
  ]
}
"""


def extract_constraints_with_pipeline(
    record: Dict,
    pipeline: LLMPipeline,
    max_text_length: int = 50000,
    log_file=None,
    max_retries: int = 5,
) -> Optional[Dict]:
    text = record.get("text", "")
    if not text:
        return None

    # Truncate very long text
    original_length = len(text)
    if original_length > max_text_length:
        truncated = text[:max_text_length]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")
        cutoff = max(last_period, last_newline, int(max_text_length * 0.9))
        text = text[:cutoff] + f"\n\n[Text truncated from {original_length} to {cutoff} characters]"
        print(
            f"Warning: Truncated clause {record.get('id', 'unknown')} from {original_length} to {cutoff} chars"
        )

    # Get context
    heading = record.get("heading", "")
    hierarchy = record.get("hierarchy", {})
    subsection_path = record.get("subsection_path", "")
    identifier = record.get("identifier", "")

    # Reset pipeline for new record
    pipeline.reset()

    # Log initial state
    if log_file:
        log_entry = {
            "record_id": record.get("id", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "llm_calls": [],
            "input": {
                "heading": heading,
                "subsection_path": subsection_path,
                "identifier": identifier,
                "text_preview": text[:500] + "..." if len(text) > 500 else text,
                "text_length": len(text),
            },
        }

    try:
        # Step 1: Analysis
        analysis_prompt = f"""Analyze this legal text from Title 26:

Section Heading: {heading}
Subsection Path: {subsection_path if subsection_path else "N/A"}
Identifier: {identifier}

Legal Text:
{text}

Identify what entities/events are mentioned and what temporal references exist."""

        analysis_response = pipeline.call_with_json_output(
            system_prompt=ANALYSIS_PROMPT,
            user_prompt=analysis_prompt,
            include_history=False,
        )

        if log_file:
            log_entry["llm_calls"].append(
                {
                    "step": "analysis",
                    "prompt": analysis_prompt,
                    "response": analysis_response,
                }
            )

        if not analysis_response:
            if log_file:
                log_entry["error"] = "Failed to parse analysis response"
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                log_file.flush()
            return None

        last_feedback = ""

        for attempt in range(1, max_retries + 1):
            generation_prompt = f"""Based on this analysis and the original legal text, reason step-by-step about the temporal (date/period) constraints and then output the final constraints in DateSMT format.

First, think internally about:
- What date variables are needed
- What temporal relationships must hold
- How to express them using only allowed DateSMT operations

Then output ONLY the final JSON object with description and constraints (no explanatory text).

Analysis:
{json.dumps(analysis_response, indent=2)}

Original Legal Text:
{text}
"""
            if last_feedback:
                generation_prompt += (
                    "\n\nFEEDBACK FROM PREVIOUS ATTEMPT:\n"
                    f"{last_feedback}\n"
                    "Regenerate the constraints, strictly obeying the rules above."
                )

            constraint_response = pipeline.call(
                system_prompt=GENERATION_PROMPT,
                user_prompt=generation_prompt,
                include_history=False,
            )

            if log_file:
                log_entry["llm_calls"].append(
                    {
                        "step": "generation",
                        "attempt": attempt,
                        "prompt": generation_prompt,
                        "response": constraint_response,
                    }
                )

            # Parse constraint response
            resp = constraint_response.strip()

            # Remove markdown code fences if present
            if "```" in resp:
                code_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
                matches = re.findall(code_block_pattern, resp, re.DOTALL)
                if matches:
                    resp = matches[-1].strip()

            # Try to extract JSON
            if not (resp.strip().startswith("{") or resp.strip() == "null"):
                json_match = re.search(r"(\{.*\}|null)", resp, re.DOTALL)
                if json_match:
                    resp = json_match.group(1).strip()

            try:
                constraint_obj = json.loads(resp)
            except json.JSONDecodeError as e:
                msg = f"Previous response was not valid JSON (parse error: {e}). Output ONLY a JSON object or null."
                last_feedback, should_return = _handle_validation_error(
                    msg, "json_parse_error", record.get("id", "unknown"), attempt, max_retries,
                    log_file, log_entry, {"raw_response": resp[:1000]}
                )
                if should_return:
                    return None
                continue

            # Check if null (no constraints)
            if constraint_obj is None:
                if log_file:
                    log_entry["result"] = "no_constraints"
                    log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    log_file.flush()
                return {"_status": "no_constraints"}

            # Validate: must be a dict
            if not isinstance(constraint_obj, dict):
                msg = "Previous response was not a JSON object. Return a JSON object with 'description' and 'constraints', or null."
                last_feedback, should_return = _handle_validation_error(
                    msg, "not_dict", record.get("id", "unknown"), attempt, max_retries,
                    log_file, log_entry, {"response_type": str(type(constraint_obj))}
                )
                if should_return:
                    return None
                continue

            # Validate: must have 'constraints' field
            if "constraints" not in constraint_obj:
                msg = "Previous response was missing the 'constraints' field. Include a 'constraints' array."
                last_feedback, should_return = _handle_validation_error(
                    msg, "missing_constraints", record.get("id", "unknown"), attempt, max_retries,
                    log_file, log_entry, {"response_keys": list(constraint_obj.keys())}
                )
                if should_return:
                    return None
                continue

            # Validate constraints by parsing them
            constraints_list = constraint_obj.get("constraints", [])
            is_valid, parser_error = _validate_constraints_with_parser(constraints_list)
            if not is_valid:
                # Include the actual constraints in feedback so LLM knows what to fix
                constraints_preview = json.dumps(constraints_list, indent=2)[:500]
                msg = (
                    f"Previous response contains invalid constraints.\n"
                    f"Parser error: {parser_error}\n"
                    f"Your constraints were:\n{constraints_preview}\n"
                    f"Please fix the invalid constraint(s)."
                )
                last_feedback, should_return = _handle_validation_error(
                    msg, "parser_error", record.get("id", "unknown"), attempt, max_retries,
                    log_file, log_entry, {"parse_error": parser_error}
                )
                if should_return:
                    return None
                continue

            # Add provenance
            constraint_obj["provenance"] = {
                "hierarchy": hierarchy,
                "subsection_path": subsection_path,
                "identifier": identifier,
                "original_text": text,
                "heading": heading,
            }

            # Keep the ID from the source file
            source_id = record.get("id", "unknown")
            constraint_obj["id"] = source_id

            if "parsed_id" in record:
                constraint_obj["parsed_id"] = record["parsed_id"]

            # Log success
            if log_file:
                log_entry["result"] = "success"
                log_entry["llm_call_count"] = pipeline.get_call_count()
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                log_file.flush()

            return constraint_obj

    except Exception as e:
        error_msg = str(e)
        if log_file:
            log_entry["error"] = f"Exception: {error_msg}"
            log_entry["exception_type"] = type(e).__name__
            log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            log_file.flush()
        print(f"Error processing clause {record.get('id', 'unknown')}: {e}")
        return None


def parse_id_range(id_range_str: str) -> Tuple[int, int]:
    """Parse ID range string like '1-50' into (start, end) tuple."""
    try:
        parts = id_range_str.split("-")
        if len(parts) != 2:
            raise ValueError("ID range must be in format 'start-end'")
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        if start < 1 or end < start:
            raise ValueError("Start must be >= 1 and end must be >= start")
        return start, end
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid ID range format: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract date/time constraints from legal text using a 2-step LLM pipeline (analysis + generation)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Input JSONL file (default: dataset/legal_doc_constraints/processed_data/filtered.jsonl)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSONL file path (default: dataset/legal_doc_constraints/constraints/constraints_2llm_YYYY-MM-DD_HH-MM-SS.jsonl)",
    )
    parser.add_argument(
        "--id-range",
        type=parse_id_range,
        help="ID range to process (e.g., '1-50' for IDs 1 through 50, inclusive)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (or set ANTHROPIC_API_KEY/OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="LLM model name (auto-detected if not specified)",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "auto"],
        default="auto",
        help="LLM provider (default: auto)",
    )
    parser.add_argument(
        "--skip-errors",
        action="store_true",
        help="Skip records that fail extraction",
    )
    parser.add_argument(
        "--max-text-length",
        type=int,
        default=50000,
        help="Maximum text length per record to send to LLM (default: 50000 chars). Longer text will be truncated.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum number of retries per record when LLM output is invalid (default: 5).",
    )

    args = parser.parse_args()

    # Resolve default paths
    root_dir = Path(__file__).resolve().parents[1]

    if args.input:
        input_path = Path(args.input)
    else:
        input_path = root_dir / "processed_data" / "filtered.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
        if "constraints_2llm_" in output_path.stem:
            timestamp = output_path.stem.replace("constraints_2llm_", "")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = root_dir / "constraints" / f"constraints_2llm_{timestamp}.jsonl"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create log file
    log_path = root_dir / "constraints" / f"two_step_llm_calls_{timestamp}.jsonl"
    log_file = open(log_path, "w", encoding="utf-8")
    print(f"Logging 2-step LLM calls to: {log_path}")

    # Initialize LLM helper
    print("Initializing 2-step LLM pipeline helper...")
    pipeline = LLMPipeline(
        api_key=args.api_key,
        model=args.model,
        provider=args.provider,
    )

    print(f"Processing records from {input_path}...")
    if args.id_range:
        print(f"ID range: {args.id_range[0]}-{args.id_range[1]} (inclusive)")
    print(f"Output: {output_path}")
    print("Using 2-step pipeline (analysis → generation)")

    total = 0
    extracted = 0
    no_constraints = 0
    failed = 0
    skipped = 0
    total_llm_calls = 0
    all_constraints = []

    with open(input_path, "r", encoding="utf-8") as f_in:
        for line in f_in:
            record = json.loads(line)
            record_id = int(record.get("id", 0))

            if args.id_range:
                start_id, end_id = args.id_range
                if record_id < start_id or record_id > end_id:
                    skipped += 1
                    continue

            total += 1

            constraint = extract_constraints_with_pipeline(
                record, pipeline, args.max_text_length, log_file, args.max_retries
            )
            total_llm_calls += pipeline.get_call_count()

            if constraint:
                if isinstance(constraint, Dict) and constraint.get("_status") == "no_constraints":
                    no_constraints += 1
                    if not args.skip_errors:
                        print(
                            f"Info: No constraints found for record ID {record_id}"
                        )
                else:
                    all_constraints.append(constraint)
                    extracted += 1
            else:
                failed += 1
                if not args.skip_errors:
                    print(
                        f"Warning: Failed to extract constraints from record ID {record_id}"
                    )

            if total % 10 == 0:
                avg_calls = total_llm_calls / total if total > 0 else 0
                print(
                    f"Processed {total} records, extracted {extracted}, no constraints {no_constraints}, failed {failed} (avg {avg_calls:.1f} calls/record)"
                )

    log_file.close()

    # Write output
    with open(output_path, "w", encoding="utf-8") as f_out:
        for constraint in all_constraints:
            f_out.write(json.dumps(constraint, ensure_ascii=False) + "\n")

    # Format output
    pretty_output_path = output_path.parent / f"{output_path.stem}_formatted.jsonl"
    format_as_pretty_jsonl(output_path, pretty_output_path)

    avg_calls = total_llm_calls / total if total > 0 else 0
    print("\nDone!")
    print(f"Total records processed: {total}")
    if args.id_range:
        print(f"Records skipped (outside ID range): {skipped}")
    print(f"Constraints extracted: {extracted}")
    print(f"No constraints found: {no_constraints}")
    print(f"Failed: {failed}")
    print(
        f"Total llm calls: {total_llm_calls} (avg {avg_calls:.1f} calls/record)"
    )
    print(f"Success rate: {extracted/total*100:.2f}%" if total > 0 else "N/A")
    print(f"Output saved to: {output_path}")
    print(f"Formatted version saved to: {pretty_output_path}")
    print(f"2-step LLM call log saved to: {log_path}")


if __name__ == "__main__":
    main()


