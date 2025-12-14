"""
LLM-based extraction of date/time constraints from legal text (Title 26).

Uses LLM to extract realistic constraints from legal text and common knowledge assumptions.

Processing:
- Processes records from filtered.jsonl
- Supports ID range specification (e.g., --id-range 1-50)
- Each record is sent individually to the LLM
- Very long text (>50k chars by default) is truncated to avoid context window limits
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

from dataset.llm import LLMClient
from datesmt.constraint_parser import ConstraintParser


# System prompt for legal document constraint extraction
LEGAL_EXTRACTION_PROMPT = """You are an expert in temporal reasoning, specializing in converting legal clauses from the U.S. Internal Revenue Code (Title 26) into precise DateSMT constraints.

Your task:  
Given a passage of legal text, extract all explicit and logically required date/period constraints and express them in the DateSMT DSL specified below.  
You must output ONLY valid JSON following the schema below.

────────────────────────────────────────────────────────
I. DateSMT DSL TYPES & DECLARATIONS
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
- Period() ONLY accepts concrete integers — you CANNOT create symbolic period variables.
- Use parentheses () to group expressions and avoid ambiguity:
  WRONG: "a + b * c" (ambiguous)
  RIGHT: "(a + b) * c" or "a + (b * c)"
  WRONG: "A -> B -> C" (chained, invalid)
  RIGHT: "(A) -> ((B) -> (C))" (nested, valid)

────────────────────────────────────────────────────────
II. DateSMT DSL ALLOWED OPERATIONS
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
- Logical operators: && (and), || (or), ! (not)
- Implication: (A) -> (B)
- Nested implication for "if A and B then C": (A) -> ((B) -> (C))
- Complex expressions: (A && B) || C, !(A || B), etc.

────────────────────────────────────────────────────────
III. FORBIDDEN EXPRESSIONS
────────────────────────────────────────────────────────
- Period ▷◁ Period  (compare dates after applying periods instead)
- Boolean arithmetic (bool + int, bool * bool, etc.)
- Function-style And(), Or(), Not() — use operators &&, ||, ! instead
- Chained implications like (A) -> (B) -> (C) — use nested: (A) -> ((B) -> (C))
- Dates outside 1900-03-01 to 2100-02-28
- Undeclared variables (except int args to Date())

────────────────────────────────────────────────────────
IV. CONSTRAINT FORMAT RULES (CRITICAL)
────────────────────────────────────────────────────────
Output is a JSON object with separate declarations and constraints:
{
  "description": "...",
  "declarations": ["variable_name: type", ...],
  "constraints": ["constraint expression", ...]
}

Where:
- "declarations": List of variable declarations (e.g., "filing_date: date", "tax_year: int", "applied: bool")
- "constraints": List of constraint strings (all constraints are ANDed together)
- Each constraint is a full boolean expression
- Use || or "or" or "OR" for OR clauses within a constraint
- Use && or "and" or "AND" for AND clauses within a constraint
- Variable declarations MUST be in the "declarations" array, NOT in "constraints"

Example:
{
  "description": "Tax filing constraints",
  "declarations": [
    "filing_date: date",
    "tax_year_start: date",
    "tax_year_end: date",
    "applied: bool",
    "offset: int"
  ],
  "constraints": [
    "filing_date >= Date(2024, 1, 1) && filing_date <= Date(2024, 12, 31)",
    "tax_year_end >= tax_year_start",
    "tax_year_end <= tax_year_start + Period(1, 0, 0)",
    "(applied == True) -> (filing_date <= tax_year_end)",
    "offset == tax_year_end.year - tax_year_start.year"
  ]
}

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
   - "declarations": array of variable declarations (e.g., ["x: date", "y: int", "flag: bool"])
   - "constraints": array of constraint expressions (e.g., ["x >= Date(2020,1,1)", "(a || b) && c"])

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
  "declarations": [
    "claim_date: date",
    "return_filing_date: date"
  ],
  "constraints": [
    "claim_date >= return_filing_date",
    "claim_date <= return_filing_date + Period(3, 0, 0)"
  ]
}

Example 2: Property access + symbolic Date constructor
Legal Text: "The estimated tax payment is due on the 15th day of the 4th month of the following taxable year."
Output:
{
  "description": "Payment due on April 15 of the year after taxable year ends",
  "declarations": [
    "taxable_year_end: date",
    "payment_due: date",
    "next_year: int"
  ],
  "constraints": [
    "next_year == taxable_year_end.year + 1",
    "payment_due == Date(next_year, 4, 15)"
  ]
}

Example 3: Boolean flag with implication
Legal Text: "If the taxpayer elects to apply the credit, the election must be made before the due date of the return."
Output:
{
  "description": "If credit election is made, it must occur before return due date",
  "declarations": [
    "credit_elected: bool",
    "election_date: date",
    "return_due_date: date"
  ],
  "constraints": [
    "(credit_elected == True) -> (election_date <= return_due_date)"
  ]
}

Example 4: OR clause for alternatives
Legal Text: "The period of limitation shall be 3 years after the return was filed, or 2 years after the tax was paid, whichever is later."
Output:
{
  "description": "Limitation period ends at the later of 3 years after filing or 2 years after payment",
  "declarations": [
    "filing_date: date",
    "payment_date: date",
    "limitation_end: date"
  ],
  "constraints": [
    "limitation_end >= filing_date + Period(3, 0, 0)",
    "limitation_end >= payment_date + Period(2, 0, 0)",
    "(limitation_end == filing_date + Period(3, 0, 0)) || (limitation_end == payment_date + Period(2, 0, 0))"
  ]
}
"""

def _validate_constraints_with_parser(constraint_obj: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate constraints by actually parsing them with the ConstraintParser.
    
    Supports both new format (separate declarations/constraints) and old format (mixed).
    
    Args:
        constraint_obj: Dictionary with 'constraints' and optionally 'declarations' fields
    
    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    constraints = constraint_obj.get("constraints", [])
    declarations = constraint_obj.get("declarations", None)
    
    if not constraints:
        return True, None
    
    try:
        parser = ConstraintParser()
        # generate_builder_code validates and parses all constraints
        parser.generate_builder_code(constraints, declarations)
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
    error_details: Optional[Dict] = None,
) -> Tuple[str, bool]:
    """
    Handle a validation error during constraint extraction.
    
    Returns:
        Tuple of (feedback_message, should_return_none).
        If should_return_none is True, the caller should return None.
    """
    if log_file:
        feedback_log = {
            "record_id": record_id,
            "timestamp": datetime.now().isoformat(),
            "attempt": attempt,
            "feedback_type": feedback_type,
            "feedback": feedback_msg,
        }
        if error_details:
            feedback_log.update(error_details)
        log_file.write(json.dumps(feedback_log, ensure_ascii=False) + "\n")
        log_file.flush()
    
    if attempt == max_retries:
        if log_file:
            error_log = {
                "record_id": record_id,
                "timestamp": datetime.now().isoformat(),
                "error": feedback_type,
            }
            if error_details:
                error_log.update(error_details)
            log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
            log_file.flush()
        return feedback_msg, True  # should return None
    
    return feedback_msg, False  # should continue


def extract_constraints_with_llm(
    record: Dict,
    llm_client: LLMClient,
    max_text_length: int = 50000,
    log_file=None,
    max_retries: int = 5,
) -> Optional[Dict]:
    """Normalize a single clause using LLM."""

    text = record.get("text", "")
    if not text:
        return None

    # Truncate very long text to avoid context window issues
    original_length = len(text)
    if original_length > max_text_length:
        truncated = text[:max_text_length]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")
        cutoff = max(last_period, last_newline, int(max_text_length * 0.9))
        text = (
            text[:cutoff]
            + f"\n\n[Text truncated from {original_length} to {cutoff} characters]"
        )
        print(
            f"Warning: Truncated clause {record.get('id', 'unknown')} "
            f"from {original_length} to {cutoff} chars"
        )

    # Build user prompt with context
    heading = record.get("heading", "")
    hierarchy = record.get("hierarchy", {})
    subsection_path = record.get("subsection_path", "")
    identifier = record.get("identifier", "")

    base_user_prompt = (
        f"Extract date/period constraints from this legal text from Title 26 (Internal Revenue Code):\n\n"
        f"Section Heading: {heading}\n"
        f"Subsection Path: {subsection_path if subsection_path else 'N/A'}\n"
        f"Identifier: {identifier}\n\n"
        f"Legal Text:\n{text}\n\n"
        "Extract ALL explicit temporal constraints and REASON about what temporal constraints "
        "are appropriate based on the legal text.\n\n"
        "IMPORTANT:\n"
        "- Output ONLY valid JSON (either a constraint object or null)\n"
        "- Do NOT include any explanatory text, reasoning, or commentary\n"
        "- REASON about what entities are mentioned in the text and what temporal relationships are necessary\n"
        "- Only return null if the text contains absolutely NO date/time/period references whatsoever\n"
    )

    last_feedback = ""

    for attempt in range(1, max_retries + 1):
        user_prompt = base_user_prompt
        if last_feedback:
            user_prompt += (
                "\n\nFEEDBACK FROM PREVIOUS ATTEMPT:\n"
                f"{last_feedback}\n"
                "Regenerate the constraints, strictly obeying the rules above."
            )

        try:
            # Call LLM
            response = llm_client.call(LEGAL_EXTRACTION_PROMPT, user_prompt)

            # Log the LLM call
            if log_file:
                log_entry = {
                    "record_id": record.get("id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "attempt": attempt,
                    "input": {
                        "heading": heading,
                        "subsection_path": subsection_path,
                        "identifier": identifier,
                        "text_preview": text[:500] + "..." if len(text) > 500 else text,
                        "text_length": len(text),
                    },
                    "output": {
                        "raw_response": response,
                        "response_length": len(response),
                    },
                }
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                log_file.flush()

            # Parse response
            resp = response.strip()

            # Remove markdown code fences if present
            if "```" in resp:
                code_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
                matches = re.findall(code_block_pattern, resp, re.DOTALL)
                if matches:
                    resp = matches[-1].strip()
                else:
                    lines = resp.split("\n")
                    if lines and lines[0].strip().startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip().startswith("```"):
                        lines = lines[:-1]
                    resp = "\n".join(lines).strip()

            # Try to extract JSON if there's text before/after
            if not (resp.strip().startswith("{") or resp.strip() == "null"):
                json_match = re.search(r"(\{.*\}|null)", resp, re.DOTALL)
                if json_match:
                    resp = json_match.group(1).strip()

            constraint_obj = None
            parse_error: Optional[str] = None

            try:
                constraint_obj = json.loads(resp)
            except json.JSONDecodeError as e:
                parse_error = str(e)

                # Strategy 1: Extract JSON object from markdown code block
                json_block_match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", resp, re.DOTALL
                )
                if json_block_match:
                    try:
                        constraint_obj = json.loads(json_block_match.group(1))
                    except json.JSONDecodeError:
                        constraint_obj = None

                # Strategy 2: Find first { ... } block (handle nested braces)
                if constraint_obj is None:
                    start_idx = resp.find("{")
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(resp)):
                            if resp[i] == "{":
                                brace_count += 1
                            elif resp[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if brace_count == 0:
                            try:
                                constraint_obj = json.loads(resp[start_idx:end_idx])
                            except json.JSONDecodeError:
                                constraint_obj = None

                # Strategy 3: Try to find JSON after common prefixes
                if constraint_obj is None:
                    json_after_prefix = re.search(
                        r"(?:Here[^\n]*:\s*)?(\{.*\})", resp, re.DOTALL | re.IGNORECASE
                    )
                    if json_after_prefix:
                        try:
                            constraint_obj = json.loads(json_after_prefix.group(1))
                        except json.JSONDecodeError:
                            constraint_obj = None

                # Strategy 4: Try to fix common JSON issues
                if constraint_obj is None:
                    fixed_response = re.sub(r",\s*}", "}", resp)
                    fixed_response = re.sub(r",\s*]", "]", fixed_response)
                    try:
                        constraint_obj = json.loads(fixed_response)
                    except json.JSONDecodeError:
                        constraint_obj = None

            # If still no success, retry with feedback
            record_id = record.get("id", "unknown")
            
            if constraint_obj is None:
                msg = (
                    f"Previous response was not valid JSON (parse error: {parse_error}). "
                    "You must output ONLY a JSON object with 'description' and 'constraints', or null."
                )
                last_feedback, should_return = _handle_validation_error(
                    msg, "json_parse_error", record_id, attempt, max_retries, log_file,
                    {"parse_error": parse_error, "response_preview": resp[:1000] if resp else "Empty"}
                )
                if should_return:
                    return None
                continue

            # Check if LLM returned null (no constraints found)
            if constraint_obj is None:
                return {"_status": "no_constraints"}

            # Validate structure: must be a dict
            if not isinstance(constraint_obj, dict):
                msg = "Previous response was not a JSON object. You must return a JSON object with 'description' and 'constraints', or null."
                last_feedback, should_return = _handle_validation_error(
                    msg, "not_dict", record_id, attempt, max_retries, log_file,
                    {"response_type": str(type(constraint_obj))}
                )
                if should_return:
                    return None
                continue

            # Validate structure: must have 'constraints' field
            if "constraints" not in constraint_obj:
                msg = "Previous response was missing the 'constraints' field. You must include a 'constraints' array."
                last_feedback, should_return = _handle_validation_error(
                    msg, "missing_constraints", record_id, attempt, max_retries, log_file,
                    {"response_keys": list(constraint_obj.keys())}
                )
                if should_return:
                    return None
                continue

            # Validate constraints by parsing them
            is_valid, parser_error = _validate_constraints_with_parser(constraint_obj)
            if not is_valid:
                # Include the actual constraints in feedback so LLM knows what to fix
                constraints_preview = json.dumps(constraint_obj.get("constraints", []), indent=2)[:500]
                if constraint_obj.get("declarations"):
                    declarations_preview = json.dumps(constraint_obj.get("declarations", []), indent=2)[:500]
                    constraints_preview = f"declarations: {declarations_preview}\nconstraints: {constraints_preview}"
                msg = (
                    f"Previous response contains invalid constraints.\n"
                    f"Parser error: {parser_error}\n"
                    f"Your constraints were:\n{constraints_preview}\n"
                    f"Please fix the invalid constraint(s)."
                )
                last_feedback, should_return = _handle_validation_error(
                    msg, "parser_error", record_id, attempt, max_retries, log_file,
                    {"parse_error": parser_error}
                )
                if should_return:
                    return None
                continue

            # Success: add provenance and return
            constraint_obj["provenance"] = {
                "hierarchy": hierarchy,
                "subsection_path": subsection_path,
                "identifier": identifier,
                "original_text": text,
                "heading": heading,
            }

            source_id = record.get("id", "unknown")
            constraint_obj["id"] = source_id

            if "parsed_id" in record:
                constraint_obj["parsed_id"] = record["parsed_id"]

            return constraint_obj

        except Exception as e:
            msg = f"Previous attempt raised an exception: {e}. Regenerate a clean JSON constraint object."
            last_feedback, should_return = _handle_validation_error(
                msg, "exception", record.get("id", "unknown"), attempt, max_retries, log_file,
                {"exception_type": type(e).__name__, "error_message": str(e)}
            )
            if should_return:
                print(f"Error processing clause {record.get('id', 'unknown')}: {e}")
                return None

    return None


def parse_id_range(id_range_str: str) -> Tuple[int, int]:
    try:
        parts = id_range_str.split('-')
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
        description="Extract date/time constraints from legal text using LLM"
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
        help="Output JSONL file path (default: dataset/legal_doc_constraints/constraints/constraints_YYYY-MM-DD_HH-MM-SS.jsonl)",
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

    # Resolve default paths relative to the legal_doc_constraints package root
    root_dir = Path(__file__).resolve().parents[1]
    
    if args.input:
        input_path = Path(args.input)
    else:
        # Default filtered.jsonl
        input_path = root_dir / "processed_data" / "filtered.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
        # Extract timestamp from output filename if it follows the pattern, otherwise use current time
        if "constraints_" in output_path.stem:
            timestamp = output_path.stem.replace("constraints_", "")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        # Generate timestamp-based filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = root_dir / "constraints" / f"constraints_{timestamp}.jsonl"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create log file with same timestamp
    log_path = root_dir / "constraints" / f"llm_calls_{timestamp}.jsonl"
    log_file = open(log_path, "w", encoding="utf-8")
    print(f"Logging LLM calls to: {log_path}")

    # Initialize LLM client
    print("Initializing LLM client...")
    llm_client = LLMClient(
        api_key=args.api_key,
        model=args.model,
        provider=args.provider
    )

    print(f"Processing records from {input_path}...")
    if args.id_range:
        print(f"ID range: {args.id_range[0]}-{args.id_range[1]} (inclusive)")
    print(f"Output: {output_path}")

    total = 0
    extracted = 0
    no_constraints = 0
    failed = 0
    skipped = 0
    all_constraints = []

    with open(input_path, "r", encoding="utf-8") as f_in:
        for line in f_in:
            record = json.loads(line)
            record_id = int(record.get("id", 0))
            
            # Check ID range if specified
            if args.id_range:
                start_id, end_id = args.id_range
                if record_id < start_id or record_id > end_id:
                    skipped += 1
                    continue
            
            total += 1

            constraint = extract_constraints_with_llm(
                record,
                llm_client,
                args.max_text_length,
                log_file,
                args.max_retries,
            )

            if constraint:
                # Check if this is a "no constraints" marker
                if isinstance(constraint, dict) and constraint.get("_status") == "no_constraints":
                    no_constraints += 1
                    if not args.skip_errors:
                        print(
                            f"Info: No constraints found for record ID {record_id} "
                            "(LLM determined no temporal constraints exist)"
                        )
                else:
                    all_constraints.append(constraint)
                    extracted += 1
            else:
                failed += 1
                if not args.skip_errors:
                    print(f"Warning: Failed to extract constraints from record ID {record_id} (parsing error or exception)")

            if total % 10 == 0:
                print(f"Processed {total} records, extracted {extracted}, no constraints {no_constraints}, failed {failed}")

    # Close log file
    log_file.close()

    # Write compact JSONL
    with open(output_path, "w", encoding="utf-8") as f_out:
        for constraint in all_constraints:
            f_out.write(json.dumps(constraint, ensure_ascii=False) + "\n")

    # Also write pretty JSONL version
    pretty_output_path = output_path.parent / f"{output_path.stem}_formatted.jsonl"
    from format_jsonl import format_as_pretty_jsonl
    format_as_pretty_jsonl(output_path, pretty_output_path)

    print(f"\nDone!")
    print(f"Total records processed: {total}")
    if args.id_range:
        print(f"Records skipped (outside ID range): {skipped}")
    print(f"Constraints extracted: {extracted}")
    print(f"No constraints found (LLM returned null): {no_constraints}")
    print(f"Failed (parsing errors/exceptions): {failed}")
    print(f"Success rate: {extracted/total*100:.2f}%" if total > 0 else "N/A")
    print(f"Output saved to: {output_path}")
    print(f"Formatted version saved to: {pretty_output_path}")
    print(f"LLM call log saved to: {log_path}")


if __name__ == "__main__":
    main()
