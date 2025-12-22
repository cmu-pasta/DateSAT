"""
Constraint generator for DATE-SMT using LLM.

This module handles constraint-specific logic including prompts, validation,
and generation workflows. It uses the universal dataset.llm module for LLM API calls.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..llm import LLMClient
except ImportError:
    # Try absolute import
    import sys
    from pathlib import Path
    dataset_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(dataset_path))
    from llm import LLMClient

try:
    from .id_counter import get_next_id
except ImportError:
    from id_counter import get_next_id

try:
    from datesmt.constraint_parser import ConstraintParser
except ImportError:
    import sys
    from pathlib import Path
    # Add repo root to path
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from datesmt.constraint_parser import ConstraintParser


def _validate_constraints_with_parser(constraint_obj: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate constraints by actually parsing them with the ConstraintParser.

    Args:
        constraint_obj: Dictionary with 'constraints' and optionally 'declarations' fields

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    constraints = constraint_obj.get("constraints", [])
    declarations = constraint_obj.get("declarations", [])

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
    batch_id: str,
    attempt: int,
    max_retries: int,
    log_file,
    error_details: Optional[Dict] = None,
) -> Tuple[str, bool]:
    """
    Handle a validation error during constraint generation.

    Returns:
        Tuple of (feedback_message, should_return_empty_list).
        If should_return_empty_list is True, the caller should return [].
    """
    if log_file:
        feedback_log = {
            "batch_id": batch_id,
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
                "batch_id": batch_id,
                "timestamp": datetime.now().isoformat(),
                "error": feedback_type,
            }
            if error_details:
                error_log.update(error_details)
            log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
            log_file.flush()
        return feedback_msg, True  # should return []

    return feedback_msg, False  # should continue


# System prompt for constraint generation
SYSTEM_PROMPT = """You are an expert in writing DateSMT constraints.

GOAL
Generate a JSON array of constraint objects for the Python DateSMT library.

RULES & OPERATIONS
- Use ONLY dates and calendar periods (no times, time zones, or DST).

VARIABLE COUNT (IMPORTANT)
- Use between 2 and 5 distinct date variables per constraint object
- Avoid “trivial” constraints unless part of a richer set
- Prefer meaningful relationships between variables (comparisons, arithmetic, range checks)

CRITICAL DATE RANGE RESTRICTIONS
- ALL dates MUST be within: 1900-03-01 to 2100-02-28 (inclusive)
- FORBIDDEN: Any date before 1900-03-01 or after 2100-02-28

Allowed operations:
  • Date ± Period → Date
  • Period ± Period → Period
  • Period × Int → Period
  • Date ▷◁ Date (▷◁ ∈ {==, !=, <, <=, >, >=})
- FORBIDDEN: Period comparisons (Period ▷◁ Period). Compare dates after adding periods instead.
- Example: (x + Period(0,1,0)) > (y + Period(0,0,31))

DateSMT SYNTAX
- Constructors: Date(year, month, day), Period(years, months, days)
- Date Variables: Any valid Python identifier (starts with letter/underscore, followed by letters/digits/underscores)
  Examples: x, y, z, var1, _var, var_123, VAR, start_date, endDate

VALID RANGES (STRICT - VIOLATIONS CAUSE ERRORS)
- Date range: 1900-03-01 <= Date <= 2100-02-28 (inclusive)
  • Year: 1900 (only months 3-12) or 1901-2099 (all months) or 2100 (only months 1-2)
  • Month: 1-12
  • Day: 1-31 (but must be valid for the month/year combination)
- CRITICAL: All concrete dates in constraints must be within 1900-03-01 to 2100-02-28
- Only concrete Period values are supported (no PeriodVar)

CONTENT DIVERSITY
Generate constraints covering:
  1) Year vs day contrasts (1 year ≠ 365/366 days) → tag: "year_vs_days"
  2) Month vs day contrasts (+1 month ≠ +31 days) → tag: "month_vs_days"
  3) Symbolic variables in date expressions like Date(x, 1, 2) or Date(x+1, 2, 1) → tag: "symbolic_date_vars"
  4) Property access on date variables like x.year, x.month, x.day → tag: "property_access"
  5) Use of logical operators like &&, ||, ! → tag: "logical_operators"

TAG-FOCUSED GENERATION (WHEN COVERAGE TAGS ARE SPECIFIED)
- When a list of allowed coverage_tags is provided, you MUST:
  • Generate ONLY constraint objects that genuinely exercise those categories
  • Set each object's coverage_tags to a subset of the allowed list
  • Focus the constraints on those behaviors (do not mix in unrelated categories)

SATISFIABILITY DIVERSITY (CRITICAL)
- Generate BOTH satisfiable (SAT) and unsatisfiable (UNSAT) constraint sets
- UNSAT examples:
  • Contradictory constraints: "x == Date(2000, 2, 29)" && "x == Date(2000, 2, 28)"
  • Impossible date ranges: "x >= Date(2100, 3, 1)" (out of allowed range)
  • Conflicting period arithmetic: "x == Date(2000, 2, 29)" && "(x + Period(1, 0, 0)) == Date(2001, 2, 29)" (2001 is not a leap year)
  • Impossible component combinations: "x.year == 2000" && "x.month == 2" && "x.day == 30" (Feb 30 doesn't exist)
- SAT examples:
  • Valid date assignments: "x == Date(2000, 2, 29)" && "x.year == 2000"
  • Consistent period arithmetic: "x == Date(2000, 2, 29)" && "(x + Period(1, 0, 0)) == Date(2001, 2, 28)"
  • Valid date ranges within bounds: "x >= Date(2000, 1, 1)" && "x <= Date(2000, 12, 31)"

AVOID TRIVIAL / MEANINGLESS CONSTRAINTS
- Do NOT add constraints that are automatically true given other constraints (tautologies)
- Do NOT restate the same condition without adding new information
- Avoid “x.month == 2” or “x.day == 29” when x is already fixed to Date(2000, 2, 29), unless this is required for a specific coverage tag (e.g., "property_access") and you REMOVE other redundant copies
- Avoid combining many redundant range checks that do not change satisfiability
- Use property access (x.year, x.month, x.day) ONLY when:
  • The object’s coverage_tags includes "property_access", or
  • It is strictly necessary to express a non-trivial constraint

DECLARATIONS AND CONSTRAINTS
- Separate declarations from constraints: use "declarations" array for variable declarations (e.g., "x: int", "y: date")
- Use "constraints" array for constraint expressions only
- All variables must be declared in "declarations" before use in "constraints", except int variables used as arguments to Date()

OUTPUT SCHEMA (STRICT)
Return ONLY a JSON array (no markdown fences, no commentary).
Each element must be an object:
{
  "description": "brief human explanation of the constraint set",
  "declarations": ["start_date: date", "end_date: date"],
  "constraints": [
    "start_date == Date(2020, 2, 28)",
    "end_date == Date(start_date.year + 1, start_date.month, start_date.day)",
    "end_date.year == start_date.year + 1",
    "start_date.month == 2"
  ],
  "coverage_tags": ["symbolic_date_vars", "property_access"]
}

COVERAGE TAG EXAMPLES
- year_vs_days:
  {
    "description": "One year vs 365 days comparison across leap and non-leap years",
    "declarations": ["leap_start: date", "leap_plus_year: date", "leap_plus_days: date"],
    "constraints": [
      "leap_start == Date(2000, 2, 29)",
      "leap_plus_year == leap_start + Period(1, 0, 0)",
      "leap_plus_year == Date(2001, 2, 28)",
      "leap_plus_days == leap_start + Period(0, 0, 365)",
      "leap_plus_days != leap_plus_year",
      "leap_plus_year.year == 2001",
      "leap_plus_days.year >= 2001"
    ],
    "coverage_tags": ["year_vs_days"]
  }
- month_vs_days:
  {
    "description": "Testing month vs days in February (28 days vs 1 month)",
    "declarations": ["x: date", "y: date", "z: date"],
    "constraints": [
      "x >= Date(2023, 1, 28)",
      "x <= Date(2023, 1, 31)",
      "(x + Period(0, 1, 0)) != (x + Period(0, 0, 28))",
      "(x + Period(0, 1, 0)) > (x + Period(0, 0, 28))",
      "y == x + Period(0, 1, 0)",
      "z == x + Period(0, 0, 28)"
    ],
    "coverage_tags": ["month_vs_days"]
  }
- symbolic_date_vars:
  {
    "description": "Symbolic years in Date constructors with linked leap behavior",
    "declarations": ["x: date", "y: date", "z: date"],
    "constraints": [
      "x == Date(2000, 2, 29)",
      "y == Date(x.year + 4, x.month, x.day)",
      "z == Date(x.year + 100, y.day-20, 28)"
    ],
    "coverage_tags": ["symbolic_date_vars"]
  }
- property_access:
  {
    "description": "Non-trivial constraints using date component access",
    "declarations": ["x: date", "y: date"],
    "constraints": [
      "x == Date(z, 2, 29)",
      "y == x + Period(1, 0, 0)",
      "y.year == x.year + 1",
      "y.month == x.month",
      "y.day == 28"
    ],
    "coverage_tags": ["property_access"]
  }
- logical_operators:
  {
    "description": "Use of logical operators like &&, ||, !",
    "declarations": ["x: date", "y: date"],
    "constraints": [
      "x == Date(2000, 2, 29)",
      "y == x + Period(1, 0, 0)",
      "(x.year == 2000 && y.year == 2001) -> (y.month == x.month && y.day == 28)",
      "!(x.year == y.year)",
      "(x.day == 29 && y.day == 28) || (x.month == 2 && y.month == 3)"
    ],
    "coverage_tags": ["logical_operators"]
  }

LOGICAL OPERATORS
- Use && for AND, || for OR within single constraint strings
- Use ! for NOT: !(condition)
- Use -> for implication: (condition) -> (consequence)
- All constraints in the array are ANDed together

STYLE FOR constraints
- Write constraints as individual strings that can be parsed by the constraint parser.
- Use simple, readable constraint expressions.
- Each constraint should be a complete boolean expression.
- Use parentheses to group expressions and avoid ambiguity.
- ALWAYS ensure all dates are within 1900-03-01 to 2100-02-28 range.
- Example format (all dates within allowed range):
  "x >= Date(2000,2,28)"
  "(x + Period(0,1,0)) > (y + Period(0,0,31))"
  "x == Date(2020,3,15)"
  "(x + Period(1,0,0)) < Date(2025,1,1)"
  "(x + Period(0,1,0) * 12) == (x + Period(1,0,0))"
  "x >= Date(2000,2,28) && x <= Date(2000,3,1)"
- BAD examples (dates out of range - DO NOT USE):
  "x == Date(1900,1,1)"  # Before 1900-03-01
  "x == Date(2100,3,1)"  # After 2100-02-28

OUTPUT REQUIREMENTS
- Output MUST be a valid JSON array of objects with the exact schema above.
- Each object must have "description", "declarations" (array of variable declarations), "constraints" (array of strings), and "coverage_tags" (array of strings).
- "declarations" contains variable declarations like "x: date" - all variables used in constraints must be declared here first (except int variables used as arguments to Date()).
- "constraints" contains constraint expressions - all constraints in the array are ANDed together.
- Select appropriate coverage_tags from the CONTENT DIVERSITY section based on what each constraint set covers.
- CRITICAL: All concrete dates MUST be within 1900-03-01 to 2100-02-28. Check all Date() constructors and ensure period arithmetic results stay in range.
- CRITICAL: Generate both SAT and UNSAT constraint sets as specified in SATISFIABILITY DIVERSITY section.
- No code fences, markdown, trailing commas, or comments.
- Use only ASCII quotes in JSON strings.
- Each constraint string must be parseable by the constraint parser."""


def _basic_schema_ok(items: Any) -> bool:
    """Validate that items is a list of constraint objects with required fields."""
    if not isinstance(items, list) or not items:
        return False

    # Check if it's a simple array of constraint strings (backward compatibility)
    if all(isinstance(item, str) for item in items):
        return True

    # Required fields for constraint objects (id is optional, added later)
    required_keys = {"description", "declarations", "constraints", "coverage_tags"}
    for it in items:
        if not isinstance(it, dict):
            return False
        # Must have all required keys
        if not required_keys.issubset(set(it.keys())):
            return False
        # Validate types
        if not isinstance(it["description"], str):
            return False
        constraints = it.get("constraints")
        if not isinstance(constraints, list) or not constraints:
            return False
        if not isinstance(it["coverage_tags"], list):
            return False
        # Validate constraint strings
        for clause in constraints:
            if not isinstance(clause, str):
                return False
        # Validate coverage tags
        if not all(isinstance(tag, str) for tag in it["coverage_tags"]):
            return False
        # Validate declarations
        declarations = it.get("declarations")
        if not isinstance(declarations, list):
            return False
        if not all(isinstance(decl, str) for decl in declarations):
            return False
    return True


def _normalize_to_dict_format(items: List[Any]) -> List[Dict]:
    """Normalize items to expected dict format with id, description, declarations, constraints, and coverage_tags.

    If items is an array of strings (backward compatibility), each string becomes its own constraint object.
    If items contains dicts, they are preserved with IDs added if needed.
    """
    result = []
    for item in items:
        if isinstance(item, str):
            # Simple string format: each string becomes a separate constraint object
            result.append({
                "id": str(get_next_id()),
                "description": f"Generated constraint: {item[:50]}{'...' if len(item) > 50 else ''}",
                "declarations": [],
                "constraints": [item],
                "coverage_tags": []
            })
        elif isinstance(item, dict):
            # Already in dict format, ensure it has an id and declarations
            constraint_dict = item.copy()
            if "id" not in constraint_dict:
                constraint_dict["id"] = str(get_next_id())
            if "declarations" not in constraint_dict:
                constraint_dict["declarations"] = []
            result.append(constraint_dict)
        else:
            raise ValueError(f"Unexpected constraint format: {type(item)}")
    return result


def _count_constraints(constraints: List[str]) -> int:
    """Count top-level constraints."""
    return len(constraints)


class ConstraintGenerator:
    """Generator for DATE-SMT constraints using LLM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
    ):
        """
        Initialize constraint generator.

        Args:
            api_key: API key for the LLM provider (overrides environment variable)
            model: Model name (uses default for provider if not specified)
            provider: Provider name - 'openai', 'anthropic', or 'auto' (default: 'auto')
        """
        self.llm_client = LLMClient(api_key=api_key, model=model, provider=provider)

    def generate_constraints(
        self,
        num_constraints: int = 10,
        retries: int = 2,
        batch_size: int = 5,
        tags: Optional[List[str]] = None,
        min_constraints_per_object: Optional[int] = None,
        max_constraints_per_object: Optional[int] = None,
        exact_constraints_per_object: Optional[int] = None,
        log_file=None
    ) -> List[Dict]:
        """
        Generate DATE-SMT constraints with validation + feedback loop and auto-repair.
        Produces a mix of SAT/UNSAT across diverse boundary categories.

        Args:
            num_constraints: Number of constraint objects to generate
            retries: Number of retry attempts for failed generations
            batch_size: Batch size for generating large constraint sets
            tags: List of coverage tags to restrict generation to. If None, all tags are allowed (default).
                  Valid tags: year_vs_days, month_vs_days, symbolic_date_vars, property_access, logical_operators 
            min_constraints_per_object: Minimum number of constraints per object (default: 5)
            max_constraints_per_object: Maximum number of constraints per object (default: 10)
            exact_constraints_per_object: Exact number of constraints per object (overrides min/max if set)
            log_file: Optional file object to log generation attempts and feedback
        """
        def _one_call(n: int, log_file=None) -> List[Dict]:
            local_last_err = None
            local_raw = ""
            local_norm = ""

            # Build prompt with tag restrictions if specified
            tag_restriction = ""
            if tags:
                tags_str = ", ".join(f'"{tag}"' for tag in tags)
                tag_restriction = (
                    f" IMPORTANT: Only generate constraints with coverage_tags from this list: [{tags_str}]. "
                    f"Each constraint object must have at least one of these tags in its coverage_tags array. "
                    f"Do not use any other tags."
                )

            # Build constraint count instructions
            constraint_count_instruction = ""
            min_c = (
                min_constraints_per_object
                if min_constraints_per_object is not None
                else 5
            )
            max_c = (
                max_constraints_per_object
                if max_constraints_per_object is not None
                else 10
            )
            if exact_constraints_per_object is not None:
                constraint_count_instruction = (
                    f" CRITICAL: Each constraint object must have exactly {exact_constraints_per_object} constraints in its 'constraints' array. "
                    f"All {n} objects must have exactly {exact_constraints_per_object} constraints."
                )
            else:
                constraint_count_instruction = (
                    f" CRITICAL: Vary the number of constraints per object. Each constraint object must have between {min_c} and {max_c} constraints "
                    f"(inclusive) in its 'constraints' array. "
                    f"Generate a diverse mix - some objects should have {min_c} constraint(s), some should have {max_c} constraints, "
                    f"and others should have various counts in between. Do NOT make all objects have the same number of constraints."
                )

            base_prompt = (
                f"Generate exactly {n} unique constraint objects as a JSON array per the OUTPUT SCHEMA. "
                f"Each object must have 'description', 'declarations' (array of variable declarations), 'constraints' (array of constraint strings), and 'coverage_tags' (array of tags).{constraint_count_instruction}{tag_restriction} "
                f"{'Ensure at least 5 distinct coverage_tags across the overall set. ' if not tags else ''}"
                f"Cover diverse edge cases (leap years, month boundaries, multi-variable relations, etc.). "
                f"Make each constraint set unique and different from the others."
            )
            
            last_feedback = ""
            batch_id = f"batch_{datetime.now().isoformat()}"
            
            for attempt in range(retries + 1):
                try:
                    # Build prompt with feedback if available
                    if last_feedback:
                        local_prompt = f"{base_prompt}\n\n{last_feedback}\n\nPlease regenerate the constraints with the corrections above."
                    else:
                        local_prompt = base_prompt
                    
                    local_raw = self.llm_client.call(SYSTEM_PROMPT, local_prompt)
                    
                    # Log the LLM call
                    if log_file:
                        call_log = {
                            "batch_id": batch_id,
                            "timestamp": datetime.now().isoformat(),
                            "attempt": attempt + 1,
                            "prompt": local_prompt[:1000],  # Truncate for readability
                            "response_preview": local_raw[:500] if local_raw else "Empty"
                        }
                        log_file.write(json.dumps(call_log, ensure_ascii=False) + "\n")
                        log_file.flush()
                    
                    # Try to parse JSON response
                    parse_error = None
                    items = None
                    try:
                        items = self.llm_client.parse_json_response(local_raw, extract_array=True)
                    except Exception as e:
                        parse_error = str(e)
                    
                    # Validate JSON structure
                    if items is None:
                        msg = (
                            f"Previous response was not valid JSON (parse error: {parse_error}). "
                            "You must output ONLY a JSON array of constraint objects per the OUTPUT SCHEMA."
                        )
                        last_feedback, should_return = _handle_validation_error(
                            msg, "json_parse_error", batch_id, attempt + 1, retries + 1, log_file,
                            {"parse_error": parse_error, "response_preview": local_raw[:1000] if local_raw else "Empty"}
                        )
                        if should_return:
                            return []
                        continue
                    
                    # Validate basic schema
                    if not _basic_schema_ok(items):
                        msg = "Previous response failed basic schema validation. Each object must have 'description', 'declarations', 'constraints', and 'coverage_tags' fields."
                        last_feedback, should_return = _handle_validation_error(
                            msg, "schema_validation_error", batch_id, attempt + 1, retries + 1, log_file,
                            {"response_preview": json.dumps(items[:2] if items else [], indent=2)[:500]}
                        )
                        if should_return:
                            return []
                        continue
                    
                    # Validate constraint counts
                    for idx, it in enumerate(items, start=1):
                        constraint_total = _count_constraints(it["constraints"])
                        if exact_constraints_per_object is not None:
                            if constraint_total != exact_constraints_per_object:
                                msg = (
                                    f"Constraint object {idx} has {constraint_total} constraints; "
                                    f"expected exactly {exact_constraints_per_object}."
                                )
                                last_feedback, should_return = _handle_validation_error(
                                    msg, "constraint_count_error", batch_id, attempt + 1, retries + 1, log_file,
                                    {"object_index": idx, "actual_count": constraint_total, "expected_count": exact_constraints_per_object}
                                )
                                if should_return:
                                    return []
                                raise ValueError(msg)
                        else:
                            if constraint_total < min_c or constraint_total > max_c:
                                msg = (
                                    f"Constraint object {idx} has {constraint_total} constraints; "
                                    f"expected between {min_c} and {max_c}."
                                )
                                last_feedback, should_return = _handle_validation_error(
                                    msg, "constraint_count_error", batch_id, attempt + 1, retries + 1, log_file,
                                    {"object_index": idx, "actual_count": constraint_total, "min_expected": min_c, "max_expected": max_c}
                                )
                                if should_return:
                                    return []
                                raise ValueError(msg)
                    
                    # Validate constraints with parser
                    for idx, it in enumerate(items, start=1):
                        is_valid, parser_error = _validate_constraints_with_parser(it)
                        if not is_valid:
                            constraints_preview = json.dumps(it.get("constraints", []), indent=2)[:500]
                            declarations_preview = json.dumps(it.get("declarations", []), indent=2)[:500]
                            msg = (
                                f"Constraint object {idx} contains invalid constraints.\n"
                                f"Parser error: {parser_error}\n"
                                f"Your declarations were:\n{declarations_preview}\n"
                                f"Your constraints were:\n{constraints_preview}\n"
                                f"Please fix the invalid constraint(s)."
                            )
                            last_feedback, should_return = _handle_validation_error(
                                msg, "parser_error", batch_id, attempt + 1, retries + 1, log_file,
                                {"object_index": idx, "parse_error": parser_error}
                            )
                            if should_return:
                                return []
                            raise ValueError(msg)
                    
                    # Success - log success
                    if log_file:
                        success_log = {
                            "batch_id": batch_id,
                            "timestamp": datetime.now().isoformat(),
                            "status": "success",
                            "attempt": attempt + 1,
                            "num_constraints": len(items)
                        }
                        log_file.write(json.dumps(success_log, ensure_ascii=False) + "\n")
                        log_file.flush()
                    
                    return items
                    
                except ValueError as e:
                    # These are validation errors that we've already handled with feedback
                    if attempt == retries:
                        # Last attempt failed
                        return []
                    continue
                except Exception as e:
                    local_last_err = e
                    error_str = str(e)
                    
                    # Check if this is an API error (auth, rate limit, etc.) that shouldn't be retried
                    is_api_error = (
                        "403" in error_str or 
                        "forbidden" in error_str.lower() or
                        "401" in error_str or
                        "unauthorized" in error_str.lower() or
                        "rate limit" in error_str.lower() or
                        "quota" in error_str.lower()
                    )
                    
                    if is_api_error:
                        # API errors shouldn't be retried - log and fail immediately
                        if log_file:
                            error_log = {
                                "batch_id": batch_id,
                                "timestamp": datetime.now().isoformat(),
                                "attempt": attempt + 1,
                                "error": "api_error",
                                "error_message": error_str
                            }
                            log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                            log_file.flush()
                        raise RuntimeError(
                            f"API error occurred (not retrying): {error_str}"
                        )
                    
                    # Try to extract and parse JSON array as fallback
                    try:
                        candidate = self.llm_client.parse_json_response(
                            local_raw if 'local_raw' in locals() else "", extract_array=True
                        )
                        if _basic_schema_ok(candidate):
                            return candidate
                    except Exception:
                        pass
                    
                    # Log unexpected error
                    if log_file:
                        error_log = {
                            "batch_id": batch_id,
                            "timestamp": datetime.now().isoformat(),
                            "attempt": attempt + 1,
                            "error": "unexpected_error",
                            "error_message": error_str
                        }
                        log_file.write(json.dumps(error_log, ensure_ascii=False) + "\n")
                        log_file.flush()
                    
                    if attempt == retries:
                        raise RuntimeError(
                            f"Batch generation failed after {retries+1} attempts: {local_last_err}"
                        )
                    continue
            
            return []

        if num_constraints <= batch_size:
            try:
                items = _one_call(num_constraints, log_file)
                return _normalize_to_dict_format(items)
            except Exception as e:
                print(f"[generate_constraints] Failed: {e}")
                return []

        # Batched path
        remaining = num_constraints
        all_items: List[Any] = []
        while remaining > 0:
            take = min(batch_size, remaining)
            try:
                batch_items = _one_call(take, log_file)
                all_items.extend(batch_items)
                remaining -= take
            except Exception as e:
                print(f"[generate_constraints] Batch failed (requested {take}): {e}")
                return []
        return _normalize_to_dict_format(all_items)

    @staticmethod
    def save_constraints(constraints: List[Dict], filename: str) -> None:
        """Save constraints to a JSON file."""
        # Create directory if it doesn't exist
        dirname = os.path.dirname(filename)
        if dirname:  # Only create directory if there's a directory path
            os.makedirs(dirname, exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(constraints, f, indent=2)
        print(f"Saved {len(constraints)} constraints to {filename}")

    @staticmethod
    def load_constraints(filename: str) -> List[Dict]:
        """Load constraints from a JSON file."""
        with open(filename, 'r') as f:
            return json.load(f)


def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate DATE-SMT constraints with LLM"
    )
    parser.add_argument(
        "--num", type=int, default=10, help="Number of constraints to generate"
    )
    parser.add_argument(
        "--output", default="generated_constraints.json", help="Output filename"
    )
    parser.add_argument("--api-key", help="API key (or set environment variable)")
    parser.add_argument(
        "--model", help="LLM model name (auto-detected if not specified)"
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "auto"],
        default="auto",
        help="LLM provider (auto-detect if not specified)",
    )
    parser.add_argument(
        "--tags",
        nargs="+",
        help="Coverage tags to restrict generation to. Valid tags: year_vs_days, month_vs_days, symbolic_date_vars, property_access, logical_operators. Default: all tags allowed",
    )
    parser.add_argument(
        "--min-constraints",
        type=int,
        help="Minimum number of constraints per constraint object (default: 5)",
    )
    parser.add_argument(
        "--max-constraints",
        type=int,
        help="Maximum number of constraints per constraint object (default: 10)",
    )
    parser.add_argument(
        "--exact-constraints",
        type=int,
        help="Exact number of constraints per constraint object (overrides min/max if set)",
    )
    args = parser.parse_args()

    # Create log file similar to legal extractor
    from pathlib import Path
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create log file with timestamp (same directory as output, matching legal extractor pattern)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = output_path.parent / f"llm_calls_{timestamp}.jsonl"
    log_file = open(log_path, "w", encoding="utf-8")
    print(f"Logging LLM calls to: {str(log_path)}")

    generator = ConstraintGenerator(api_key=args.api_key, model=args.model, provider=args.provider)
    constraints = generator.generate_constraints(
        args.num,
        tags=args.tags,
        min_constraints_per_object=args.min_constraints,
        max_constraints_per_object=args.max_constraints,
        exact_constraints_per_object=args.exact_constraints,
        log_file=log_file
    )
    
    log_file.close()
    
    if constraints:
        generator.save_constraints(constraints, args.output)
        print(
            f"Successfully generated {len(constraints)} constraints using {generator.llm_client.provider.upper()}"
        )
    else:
        print("Failed to generate constraints")


if __name__ == "__main__":
    main()

