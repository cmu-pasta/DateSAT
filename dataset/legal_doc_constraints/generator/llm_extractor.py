"""
LLM-based extraction of date/time constraints from legal text (Title 26).

Uses LLM to extract meaningful constraints from legal text and add common knowledge
assumptions (e.g., marriage date constraints based on birthdays).

Processing:
- Processes records from filtered.jsonl
- Supports ID range specification (e.g., --id-range 1-50)
- Each record is sent individually to the LLM
- Very long text (>50k chars by default) is truncated to avoid context window limits
- Automatically generates coverage tags based on constraint content
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add dataset to path for llm.py import
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataset.llm import LLMClient
import re

DATE_PATTERN = re.compile(r"Date\(([^)]*)\)")
PERIOD_PATTERN = re.compile(r"Period\(([^)]*)\)")


def _flatten_constraints(constraints: List) -> List[str]:
    flat: List[str] = []
    for item in constraints:
        if isinstance(item, list):
            flat.extend(_flatten_constraints(item))
        else:
            flat.append(item)
    return flat


def _find_invalid_date_period(constraints: List) -> Tuple[bool, Optional[str]]:
    def _is_valid_numeric(arg: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\d+", arg.strip()))

    for constraint in _flatten_constraints(constraints):
        for pattern in (DATE_PATTERN, PERIOD_PATTERN):
            for match in pattern.finditer(constraint):
                args = [arg.strip() for arg in match.group(1).split(",")]
                if len(args) != 3:
                    return True, constraint
                for arg in args:
                    if not _is_valid_numeric(arg):
                        return True, constraint
    return False, None


def _generate_coverage_tags(constraints: List) -> List[str]:
    """Generate coverage tags based on constraint content."""
    tags = ["tax_law"]  # All legal constraints get this tag

    # Flatten constraints (handle CNF format)
    constraint_strings = []
    for item in constraints:
        if isinstance(item, list):
            # OR clause - check all alternatives
            constraint_strings.extend(item)
        else:
            constraint_strings.append(item)

    # Check for period operations
    has_year_period = False
    has_month_period = False
    has_day_period = False
    has_multiple_periods = False

    for constraint_str in constraint_strings:
        # Check for Period operations
        if "Period(" in constraint_str:
            # Extract period components
            period_match = re.search(r'Period\((-?\d+),\s*(-?\d+),\s*(-?\d+)\)', constraint_str)
            if period_match:
                years, months, days = map(int, period_match.groups())
                if years != 0:
                    has_year_period = True
                if months != 0:
                    has_month_period = True
                if days != 0:
                    has_day_period = True

                # Check if multiple non-zero components
                non_zero = sum(1 for x in [years, months, days] if x != 0)
                if non_zero > 1:
                    has_multiple_periods = True

    # Add period-related tags
    if has_year_period and has_day_period:
        tags.append("year_vs_days")
    if has_month_period and has_day_period:
        tags.append("month_vs_days")
    if has_multiple_periods:
        tags.append("multi_period")

    # Check for OR clauses (alternatives)
    has_or_clause = any(isinstance(item, list) and len(item) > 1 for item in constraints)
    if has_or_clause:
        tags.append("alternative")

    # Check for leap year dates (February 29 or dates around Feb 28/29)
    for constraint_str in constraint_strings:
        if re.search(r'Date\([^,]+,\s*2,\s*(28|29)\)', constraint_str):
            tags.append("leap_year")
            break

    # Check for end-of-month patterns (dates with day 28, 29, 30, 31)
    for constraint_str in constraint_strings:
        if re.search(r'Date\([^,]+,\s*\d+,\s*(28|29|30|31)\)', constraint_str):
            tags.append("eom")
            break

    return tags

# System prompt for legal document constraint extraction
LEGAL_EXTRACTION_PROMPT = """You are an expert in converting legal temporal clauses from Title 26 (Internal Revenue Code) into DateSMT constraints.

GOAL
Extract date/period constraints from legal text and convert them to DateSMT format. Additionally, add common knowledge constraints that are logically implied but not explicitly stated in the text.

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
  * Date() CANNOT accept variables as parameters (e.g., Date(calendar_year, 12, 15) is INVALID)
  * To use a variable year/month/day, create a date variable and use constraints to relate it to concrete dates
- Date Variables: Use meaningful names (e.g., filing_date, payment_date, assessment_date, close_of_year, claim_date, marriage_date, spouse_birthday, individual_birthday)
  * Date variables are used directly in constraints (e.g., filing_date >= Date(2020, 1, 1))
  * Date variables can be compared to concrete dates or other date variables
  * To express “end of the same year as X”, use date variables and Period arithmetic instead of Date(X.year(), 12, 31), e.g.:
    - current_year_end >= current_year_start
    - current_year_end <= current_year_start + Period(1, 0, 0) + Period(0, 0, 1)
    - current_year_end == current_year_start + Period(0, 11, 30)
- Valid ranges: 1900-03-01 <= Date <= 2100-02-28, 1<=month<=12, 1<=day<=31

CONSTRAINT FORMAT (CNF - Conjunctive Normal Form)
The "constraints" field supports Conjunctive Normal Form (CNF) where:
- Each element can be a string (single constraint) or a list of strings (OR clause)
- All top-level constraints are ANDed together
- Lists of strings are ORed together

Examples:
- Simple AND: ["filing_date >= Date(2020, 1, 1)", "claim_date <= filing_date + Period(3, 0, 0)"]
  → (filing_date >= Date(2020, 1, 1)) AND (claim_date <= filing_date + Period(3, 0, 0))

- With OR clause: [["claim_date <= filing_date + Period(3, 0, 0)", "claim_date <= payment_date + Period(2, 0, 0)"], "filing_date >= Date(2020, 1, 1)"]
  → ((claim_date <= filing_date + Period(3, 0, 0)) OR (claim_date <= payment_date + Period(2, 0, 0))) AND (filing_date >= Date(2020, 1, 1))

Use OR clauses when the legal text has alternatives like "either X or Y" or "whichever is later/earlier".

REASONING ABOUT CONSTRAINTS
You must actively reason about what temporal constraints are appropriate based on the legal text. Do NOT automatically add constraints for entities that are not mentioned in the text.

CRITICAL RULES:
1. **Only add constraints for entities/events actually mentioned in the text**
   - If the text mentions "married individual" or "spouse", you may infer marriage-related constraints
   - If the text mentions "filing", you may infer filing_date constraints
   - If the text mentions "taxable year", you may infer tax year boundary constraints
   - DO NOT add constraints for entities that are not mentioned (e.g., don't add marriage_date constraints if the text only talks about tax rates)

2. **Reason about what temporal relationships are necessary**
   - What dates/periods are explicitly mentioned in the text?
   - What temporal relationships between these dates are required by the legal provision?
   - What common knowledge constraints are necessary for the provision to make temporal sense?
   - Only add constraints that are logically required for the legal provision to be meaningful

3. **Examples of appropriate reasoning:**
   - If text mentions "married individual filing jointly" → marriage must occur before filing, so add: marriage_date <= filing_date
   - If text mentions "taxable year" → tax year has boundaries, so add: taxable_year_end >= taxable_year_start, taxable_year_end <= taxable_year_start + Period(1, 0, 0) + Period(0, 0, 1)
   - If text mentions "filing" and "taxable year" → filing typically occurs after tax year ends, so add: filing_date >= taxable_year_end
   - If text mentions "spouse" → marriage cannot occur before birthdays, so add: marriage_date >= spouse_birthday, marriage_date >= individual_birthday
   - If text only mentions tax rates without dates → focus on tax year boundaries, not marriage dates

4. **What NOT to do:**
   - Don't add marriage_date constraints if the text doesn't mention marriage, spouse, or married individuals
   - Don't add birth_date constraints if the text doesn't mention birth, age, or related concepts
   - Don't add constraints for entities that aren't relevant to the legal provision
   - Don't add constraints just because they're "common knowledge" - they must be relevant to THIS text

5. **When to add common knowledge constraints:**
   - Only when the entities are mentioned in the text
   - Only when the temporal relationship is necessary for the legal provision to make sense
   - When the constraint helps express the temporal logic of the provision

CONTEXT AWARENESS
- Understand what the constraint actually means in legal context
- Use appropriate variable names that reflect the legal concept
- Combine related constraints from the same clause when they form a logical set
- Handle conditional logic: "If X, then Y must occur within Z period"
- Handle alternatives: "Either within 3 years OR within 2 years of payment" → use OR clause
- Extract concrete dates when mentioned (e.g., "January 1, 2020")
- For symbolic events (e.g., "filing_date", "close of taxable year"), use descriptive variable names

OUTPUT FORMAT - CRITICAL
You MUST output ONLY valid JSON. Do NOT include any explanatory text, reasoning, or commentary before or after the JSON.
Output ONLY one of the following:
1. A JSON object with "description" and "constraints" fields
2. The literal value: null

OUTPUT SCHEMA
Return a JSON object (not an array):
{
  "description": "Brief explanation of the constraint set",
  "constraints": ["constraint1", "constraint2", ...] or [["or_constraint1", "or_constraint2"], "and_constraint1", ...]
}

IMPORTANT - CONSTRAINT INFERENCE
- Extract ALL explicit temporal constraints from the legal text
- REASON about what temporal constraints are appropriate based on what's actually in the text
- Only add constraints for entities/events that are mentioned or clearly implied in the legal text
- For entities mentioned in the text, infer necessary temporal relationships:
  * If text mentions "married individual" or "spouse" → infer marriage_date constraints relative to filing and tax year
  * If text mentions "filing" → infer filing_date constraints relative to tax year boundaries
  * If text mentions "taxable year" or "taxable income" → infer tax year start/end date constraints
  * If text mentions events or actions → infer temporal ordering constraints between those events
- DO NOT add constraints for entities not mentioned (e.g., don't add marriage_date if text only discusses tax rates)
- AVOID returning null unless the text contains absolutely NO date/time/period references whatsoever
- Be logical and context-aware - only add constraints that are necessary for THIS legal provision
- Use concrete dates when available, symbolic variables for events
- Use OR clauses (lists) when the legal text has alternatives

EXAMPLES

Example 1: Simple deadline constraint
Legal Text: "A claim for credit or refund of an overpayment must be filed within 3 years from the time the return was filed."
Output:
{
  "description": "Claim for refund must be filed within 3 years of return filing",
  "constraints": [
    "claim_date <= filing_date + Period(3, 0, 0)",
    "claim_date >= filing_date"
  ]
}

Example 2: Marriage-related constraint with common knowledge
Legal Text: "The spouse is considered as spouse if the marriage date should be on or before December 31 of the taxable year."
Output:
{
  "description": "Spouse qualification requires marriage by end of taxable year, plus common knowledge that marriage cannot occur before birthdays",
  "constraints": [
    "marriage_date <= taxable_year_end",
    "marriage_date >= spouse_birthday",
    "marriage_date >= individual_birthday",
    "taxable_year_end >= taxable_year_start",
    "taxable_year_end <= taxable_year_start + Period(1, 0, 0)"
  ]
}
Note: Use date variables (like taxable_year_end) for symbolic dates. Date() constructor only accepts concrete integers like Date(2020, 12, 31).

Example 3: Effective date constraint
Legal Text: "This section applies to taxable years beginning after December 31, 2020."
Output:
{
  "description": "Section applies to taxable years beginning after December 31, 2020",
  "constraints": [
    "taxable_year_start >= Date(2021, 1, 1)",
    "taxable_year_end >= taxable_year_start"
  ]
}

Example 4: Inferring constraints from context (no explicit dates)
Legal Text: "(a) Married individuals filing joint returns... There is hereby imposed on the taxable income of every married individual... a tax determined in accordance with the following table..."
Reasoning: The text mentions "married individual" and "taxable income", which implies:
- Marriage must occur before filing (to file jointly, you must be married)
- Filing relates to taxable year (tax is imposed on taxable income)
- Tax year has boundaries
Output:
{
  "description": "Married individuals filing joint returns - temporal constraints based on entities mentioned",
  "constraints": [
    "marriage_date <= filing_date",
    "filing_date >= taxable_year_end",
    "taxable_year_end >= taxable_year_start",
    "taxable_year_end <= taxable_year_start + Period(1, 0, 0) + Period(0, 0, 1)"
  ]
}
Note: We only add constraints for entities mentioned (married individual → marriage_date, filing, taxable income → tax year). We don't add birthday constraints unless the text mentions age, birth, or related concepts.
"""


def extract_constraints_with_llm(record: Dict, llm_client: LLMClient, max_text_length: int = 50000, log_file=None) -> Optional[Dict]:
    """Normalize a single clause using LLM.

    Args:
        record: Clause record from candidates.jsonl
        llm_client: LLM client instance
        max_text_length: Maximum text length to send to LLM (default: 50000 chars)
                        Longer text will be truncated with a warning.
    """
    text = record.get("text", "")
    if not text:
        return None

    # Truncate very long text to avoid context window issues
    original_length = len(text)
    if original_length > max_text_length:
        # Try to truncate at sentence boundary
        truncated = text[:max_text_length]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        # Use the later of period or newline, but at least keep 90% of max_length
        cutoff = max(last_period, last_newline, int(max_text_length * 0.9))
        text = text[:cutoff] + f"\n\n[Text truncated from {original_length} to {cutoff} characters]"
        print(f"Warning: Truncated clause {record.get('id', 'unknown')} from {original_length} to {cutoff} chars")

    # Build user prompt with context
    heading = record.get("heading", "")
    hierarchy = record.get("hierarchy", {})
    subsection_path = record.get("subsection_path", "")
    identifier = record.get("identifier", "")

    user_prompt = f"""Extract date/period constraints from this legal text from Title 26 (Internal Revenue Code):

Section Heading: {heading}
Subsection Path: {subsection_path if subsection_path else "N/A"}
Identifier: {identifier}

Legal Text:
{text}

Extract ALL explicit temporal constraints and REASON about what temporal constraints are appropriate based on the legal text.

IMPORTANT: 
- Output ONLY valid JSON (either a constraint object or null)
- Do NOT include any explanatory text, reasoning, or commentary
- REASON about what entities are mentioned in the text and what temporal relationships are necessary
- Only add constraints for entities/events actually mentioned or clearly implied in the text
- Do NOT add constraints for entities not mentioned (e.g., don't add marriage_date if text only discusses tax rates)
- Only return null if the text contains absolutely NO date/time/period references whatsoever

Return constraints in DateSMT format."""

    try:
        # Call LLM using the call method from dataset/llm.py
        response = llm_client.call(LEGAL_EXTRACTION_PROMPT, user_prompt)
        
        # Log the LLM call
        if log_file:
            log_entry = {
                "record_id": record.get("id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "input": {
                    "heading": heading,
                    "subsection_path": subsection_path,
                    "identifier": identifier,
                    "text_preview": text[:500] + "..." if len(text) > 500 else text,
                    "text_length": len(text)
                },
                "output": {
                    "raw_response": response,
                    "response_length": len(response)
                }
            }
            log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            log_file.flush()

        # Parse response
        response = response.strip()

        # Remove markdown code fences if present (handle cases where LLM includes explanatory text)
        if "```" in response:
            # Find all code blocks
            code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
            matches = re.findall(code_block_pattern, response, re.DOTALL)
            if matches:
                # Use the last code block (most likely to be the JSON response)
                response = matches[-1].strip()
            else:
                # Fallback: remove markdown fences manually
                lines = response.split("\n")
                if lines[0].strip().startswith("```"):
                    # Remove first line (opening fence)
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    # Remove last line (closing fence)
                    lines = lines[:-1]
                response = "\n".join(lines).strip()
        
        # Also try to extract JSON if there's text before/after
        # Look for JSON object or null
        if not (response.strip().startswith("{") or response.strip() == "null"):
            # Try to find JSON in the response
            json_match = re.search(r'(\{.*\}|null)', response, re.DOTALL)
            if json_match:
                response = json_match.group(1).strip()

        # Try to parse as JSON
        constraint_obj = None
        parse_error = None
        
        try:
            constraint_obj = json.loads(response)
        except json.JSONDecodeError as e:
            parse_error = str(e)
            # Try multiple strategies to extract JSON
            
            # Strategy 1: Extract JSON object from markdown code block
            json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_block_match:
                try:
                    constraint_obj = json.loads(json_block_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Strategy 2: Find first { ... } block (handle nested braces)
            if constraint_obj is None:
                # Find the first { and then match balanced braces
                start_idx = response.find('{')
                if start_idx != -1:
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(response)):
                        if response[i] == '{':
                            brace_count += 1
                        elif response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    if brace_count == 0:
                        try:
                            constraint_obj = json.loads(response[start_idx:end_idx])
                        except json.JSONDecodeError:
                            pass
            
            # Strategy 3: Try to find JSON after common prefixes
            if constraint_obj is None:
                # Look for JSON after "Here is" or "Here's" or similar
                json_after_prefix = re.search(r'(?:Here[^\n]*:\s*)?(\{.*\})', response, re.DOTALL | re.IGNORECASE)
                if json_after_prefix:
                    try:
                        constraint_obj = json.loads(json_after_prefix.group(1))
                    except json.JSONDecodeError:
                        pass
            
            # Strategy 4: Try to fix common JSON issues
            if constraint_obj is None:
                # Remove trailing commas before closing braces/brackets
                fixed_response = re.sub(r',\s*}', '}', response)
                fixed_response = re.sub(r',\s*]', ']', fixed_response)
                try:
                    constraint_obj = json.loads(fixed_response)
                except json.JSONDecodeError:
                    pass

        # If still no success, log the error
        if constraint_obj is None:
            if log_file:
                error_log = {
                    "record_id": record.get("id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "error": "JSON parsing failed",
                    "parse_error": parse_error,
                    "response_preview": response[:1000] if response else "Empty response"
                }
                log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                log_file.flush()
            return None

        # Check if LLM returned null (no constraints found)
        if constraint_obj is None:
            # This is a valid response - LLM determined no constraints exist
            return {"_status": "no_constraints"}

        # Validate structure
        if not isinstance(constraint_obj, dict):
            if log_file:
                error_log = {
                    "record_id": record.get("id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "error": "Response is not a dictionary",
                    "response_type": str(type(constraint_obj)),
                    "response_preview": str(constraint_obj)[:500]
                }
                log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                log_file.flush()
            return None

        if "constraints" not in constraint_obj:
            if log_file:
                error_log = {
                    "record_id": record.get("id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "error": "Response missing 'constraints' field",
                    "response_keys": list(constraint_obj.keys()) if isinstance(constraint_obj, dict) else None,
                    "response_preview": json.dumps(constraint_obj, indent=2)[:500]
                }
                log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                log_file.flush()
            return None

        # Remove coverage_tags if present (we don't generate them for legal documents)
        if "coverage_tags" in constraint_obj:
            del constraint_obj["coverage_tags"]

        # Validate Date/Period constructors to ensure only numeric literals in Date()/Period()
        invalid, offending = _find_invalid_date_period(constraint_obj.get("constraints", []))
        if invalid:
            if log_file:
                error_log = {
                    "record_id": record.get("id", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "error": "Invalid Date/Period constructor usage",
                    "invalid_constraint": offending,
                }
                log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                log_file.flush()
            return None

        # Add provenance
        constraint_obj["provenance"] = {
            "hierarchy": hierarchy,
            "subsection_path": subsection_path,
            "identifier": identifier,
            "original_text": text,
            "heading": heading,
        }

        # Keep the ID from the source file (filtered.jsonl)
        source_id = record.get("id", "unknown")
        constraint_obj["id"] = source_id
        
        # Also preserve parsed_id if available
        if "parsed_id" in record:
            constraint_obj["parsed_id"] = record["parsed_id"]

        return constraint_obj

    except Exception as e:
        error_msg = str(e)
        if log_file:
            error_log = {
                "record_id": record.get("id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "error": "Exception during processing",
                "exception_type": type(e).__name__,
                "error_message": error_msg
            }
            log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
            log_file.flush()
        print(f"Error processing clause {record.get('id', 'unknown')}: {e}")
        return None


def parse_id_range(id_range_str: str) -> Tuple[int, int]:
    """Parse ID range string like '1-50' into (start, end) tuple."""
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

            constraint = extract_constraints_with_llm(record, llm_client, args.max_text_length, log_file)

            if constraint:
                # Check if this is a "no constraints" marker
                if isinstance(constraint, dict) and constraint.get("_status") == "no_constraints":
                    no_constraints += 1
                    if not args.skip_errors:
                        print(f"Info: No constraints found for record ID {record_id} (LLM determined no temporal constraints exist)")
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
