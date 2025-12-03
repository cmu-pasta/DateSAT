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

# Add dataset to path for imports
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataset.llm import LLMPipeline
import re

# Import formatting function
from format_jsonl import format_as_pretty_jsonl

DATE_PATTERN = re.compile(r"Date\(([^)]*)\)")
PERIOD_PATTERN = re.compile(r"Period\(([^)]*)\)")
INT_COMPARE_PATTERN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|<=|>=|<|>)\s*([+-]?\d+)\b"
)


def _flatten_constraints(constraints: List) -> List[str]:
    """Yield constraint strings from CNF structure."""
    flat: List[str] = []
    for item in constraints:
        if isinstance(item, list):
            flat.extend(_flatten_constraints(item))
        else:
            flat.append(item)
    return flat


def _find_invalid_date_period(constraints: List) -> Tuple[bool, Optional[str]]:
    """Return (True, constraint) if invalid Date/Period constructor usage is found."""

    def _is_valid_numeric(arg: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\d+", arg.strip()))

    for constraint in _flatten_constraints(constraints):
        for pattern, name in ((DATE_PATTERN, "Date"), (PERIOD_PATTERN, "Period")):
            for match in pattern.finditer(constraint):
                args = [arg.strip() for arg in match.group(1).split(",")]
                expected_args = 3
                if len(args) != expected_args:
                    return True, constraint
                for arg in args:
                    if not _is_valid_numeric(arg):
                        return True, constraint
        # Also reject integer variable comparisons like "calendar_year > 2003"
        if INT_COMPARE_PATTERN.search(constraint):
            return True, constraint
    return False, None


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

GENERATION_PROMPT = """You are generating DateSMT constraints for legal text from Title 26.

RULES & OPERATIONS
- Use ONLY dates variables or concrete dates and concrete calendar periods (no times, time zones, or DST).
- Date range: 1900-03-01 to 2100-02-28 (simple leap-year rules apply).
- Allowed operations (Date can be a variable or a concrete date):
  • Date ± Period → Date
  • Period ± Period → Period
  • Period * Int → Period
  • Date ▷◁ Date (▷◁ ∈ {==, !=, <, <=, >, >=})
- FORBIDDEN: Period comparisons (Period ▷◁ Period). Compare dates after adding periods instead.

DateSMT SYNTAX - CRITICAL RULES
- Constructors: Date(year, month, day), Period(years, months, days)
  * Date() constructor ONLY accepts concrete integers (e.g., Date(2020, 12, 31))
  * Date() CANNOT accept variables as parameters - THIS IS INVALID:
    Date(current_year, 1, 1) - INVALID (current_year is a variable)
    Date(calendar_year, 12, 15) - INVALID (calendar_year is a variable)
    Date(tax_year, 1, 1) - INVALID (tax_year is a variable)
  * CORRECT: Date(2020, 1, 1) - VALID (all concrete integers)
  
- How to handle variable years/dates:
  * If you need a date that depends on a variable year, create a DATE VARIABLE (not a Date() constructor)
  * Example: Instead of Date(current_year, 12, 15), use a date variable like "prescription_deadline"
  * Then relate it to other dates using constraints:
    - prescription_deadline >= Date(1900, 12, 15)
    - prescription_deadline <= Date(2100, 12, 15)
    - prescription_deadline == some_other_date + Period(1, 0, 0)  (if it's one year after)
  
- Date Variables: Use meaningful names (e.g., filing_date, payment_date, assessment_date, close_of_year, claim_date, marriage_date, spouse_birthday, individual_birthday, taxable_year_start, taxable_year_end, prescription_deadline)
  * Date variables are used directly in constraints (e.g., filing_date >= Date(2020, 1, 1))
  * Date variables can be compared to concrete dates or other date variables
  * To express “end of the same year as X”, use date variables and Period arithmetic instead of Date(X.year(), 12, 31), e.g.:
    - current_year_end >= current_year_start
    - current_year_end <= current_year_start + Period(1, 0, 0) + Period(0, 0, 1)
    - current_year_end == current_year_start + Period(0, 11, 30)   # December 31 if current_year_start is January 1
  * Date variables can be used in arithmetic: filing_date + Period(3, 0, 0)
  
- Valid ranges: 1900-03-01 <= Date <= 2100-02-28, 1<=month<=12, 1<=day<=31

CONSTRAINT FORMAT (CNF - Conjunctive Normal Form)
The "constraints" field supports Conjunctive Normal Form (CNF) where:
- Each element can be a string (single constraint) or a list of strings (OR clause)
- All top-level constraints are ANDed together
- Lists of strings are ORed together

Generate the constraints based on the reasoning provided. Output ONLY valid JSON:
{
  "description": "Brief explanation of the constraint set",
  "constraints": ["constraint1", "constraint2", ...] or [["or_constraint1", "or_constraint2"], "and_constraint1", ...]
}

If no constraints can be generated, return null."""


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
                last_feedback = (
                    f"Previous response was not valid JSON (parse error: {e}). "
                    "You must output ONLY a JSON object with 'description' and 'constraints', or null."
                )
                if log_file:
                    feedback_log = {
                        "record_id": record.get("id", "unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempt,
                        "feedback_type": "parse_error",
                        "feedback": last_feedback,
                    }
                    log_file.write(json.dumps(feedback_log, ensure_ascii=False) + "\n")
                    log_file.flush()
                if attempt == max_retries:
                    if log_file:
                        log_entry["error"] = "Failed to parse constraint JSON"
                        log_entry["raw_response"] = resp[:1000]
                        log_file.write(
                            json.dumps(log_entry, ensure_ascii=False) + "\n"
                        )
                        log_file.flush()
                    return None
                continue

            # Check if null
            if constraint_obj is None:
                if log_file:
                    log_entry["result"] = "no_constraints"
                    log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    log_file.flush()
                return {"_status": "no_constraints"}

            # Validate structure
            if not isinstance(constraint_obj, dict):
                last_feedback = (
                    "Previous response was not a JSON object. "
                    "You must return a JSON object with 'description' and 'constraints', or null."
                )
                if log_file:
                    feedback_log = {
                        "record_id": record.get("id", "unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempt,
                        "feedback_type": "not_dict",
                        "feedback": last_feedback,
                    }
                    log_file.write(json.dumps(feedback_log, ensure_ascii=False) + "\n")
                    log_file.flush()
                if attempt == max_retries:
                    if log_file:
                        log_entry["error"] = "Response is not a dictionary"
                        log_entry["response_type"] = str(type(constraint_obj))
                        log_entry["response_preview"] = str(constraint_obj)[:500]
                        log_file.write(
                            json.dumps(log_entry, ensure_ascii=False) + "\n"
                        )
                        log_file.flush()
                    return None
                continue

            if "constraints" not in constraint_obj:
                last_feedback = (
                    "Previous response was missing the 'constraints' field. "
                    "You must include a 'constraints' array in the JSON object."
                )
                if log_file:
                    feedback_log = {
                        "record_id": record.get("id", "unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempt,
                        "feedback_type": "missing_constraints_field",
                        "feedback": last_feedback,
                    }
                    log_file.write(json.dumps(feedback_log, ensure_ascii=False) + "\n")
                    log_file.flush()
                if attempt == max_retries:
                    if log_file:
                        log_entry["error"] = "Response missing 'constraints' field"
                        log_entry["response_keys"] = (
                            list(constraint_obj.keys())
                            if isinstance(constraint_obj, dict)
                            else None
                        )
                        log_entry["response_preview"] = json.dumps(
                            constraint_obj, indent=2
                        )[:500]
                        log_file.write(
                            json.dumps(log_entry, ensure_ascii=False) + "\n"
                        )
                        log_file.flush()
                    return None
                continue

            # Remove coverage_tags if present
            if "coverage_tags" in constraint_obj:
                del constraint_obj["coverage_tags"]

            # Validate Date/Period constructors use only numeric literals
            invalid, offending = _find_invalid_date_period(
                constraint_obj.get("constraints", [])
            )
            if invalid:
                last_feedback = (
                    "Previous response used invalid Date(...) or Period(...) constructors. "
                    f"The offending constraint was: {offending}. "
                    "All arguments to Date(...) and Period(...) must be plain integer literals."
                )
                if log_file:
                    feedback_log = {
                        "record_id": record.get("id", "unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempt,
                        "feedback_type": "invalid_date_period",
                        "feedback": last_feedback,
                        "invalid_constraint": offending,
                    }
                    log_file.write(json.dumps(feedback_log, ensure_ascii=False) + "\n")
                    log_file.flush()
                if attempt == max_retries:
                    if log_file:
                        log_entry["error"] = "Invalid Date/Period constructor usage"
                        log_entry["invalid_constraint"] = offending
                        log_file.write(
                            json.dumps(log_entry, ensure_ascii=False) + "\n"
                        )
                        log_file.flush()
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


