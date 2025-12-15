"""
Constraint generator for DATE-SMT using LLM.

This module handles constraint-specific logic including prompts, validation,
and generation workflows. It uses the universal dataset.llm module for LLM API calls.
"""

import json
import os
from typing import Any, Dict, List, Optional

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

# System prompt for constraint generation
SYSTEM_PROMPT = """You are an expert in writing DateSMT constraints.

GOAL
Generate a JSON array of constraint objects for the Python DateSMT library.

RULES & OPERATIONS
- Use ONLY dates and calendar periods (no times, time zones, or DST).
- Date range: 1900-03-01 to 2100-02-28 (simple leap-year rules apply).
- Allowed operations:
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
- Valid ranges: 1900-03-01 <= Date <= 2100-02-28, 1<=month<=12, 1<=day<=31
- Only concrete Period values are supported (no PeriodVar)

CONTENT DIVERSITY
Generate constraints covering:
  1) Leap year handling (Feb 28/29) → tag: "leap_year"
  2) End-of-month rollovers (30 vs 31 vs 28/29) → tag: "eom"
  3) Year vs day contrasts (1 year ≠ 365/366 days) → tag: "year_vs_days"
  4) Month vs day contrasts (+1 month ≠ +31 days) → tag: "month_vs_days"
  5) Symbolic date variables (x, y, z) → tag: "symbolic_date_vars" # TODO: update this prompt!!
- Aim for ~70% satisfiable constraints.

OUTPUT SCHEMA (STRICT)
Return ONLY a JSON array (no markdown fences, no commentary).
Each element must be an object:
{
  "description": "brief human explanation of the constraint set",
  "constraints": [["x >= Date(2000,2,28)", "x <= Date(2000,2,29)"], "x != Date(2000,3,1)"],
  "coverage_tags": ["leap_boundary", "eom"]
}

CONSTRAINT FORMAT (CNF - Conjunctive Normal Form)
The "constraints" field supports Conjunctive Normal Form (CNF) where:
- Each element can be a string (single constraint) or a list of strings (OR clause)
- All top-level constraints are ANDed together
- Lists of strings are ORed together
- Include OR clauses regularly: aim for at least one third of the constraint objects to contain at least one OR clause (list of strings). These OR clauses count as a single constraint toward any min/max constraint requirements.

Examples:
- Simple AND: ["x >= Date(2000,2,28)", "x <= Date(2000,3,1)"] → (x >= Date(2000,2,28)) AND (x <= Date(2000,3,1))
- With OR clause: [["x >= Date(2000,2,28)", "x <= Date(2000,2,29)"], "x != Date(2000,3,1)"] → ((x >= Date(2000,2,28)) OR (x <= Date(2000,2,29))) AND (x != Date(2000,3,1))
- Mixed: ["x >= Date(2000,1,1)", ["x <= Date(2000,2,28)", "x >= Date(2000,3,1)"], "y == x + Period(0,1,0)"]

STYLE FOR constraints
- Write constraints as individual strings that can be parsed by the constraint parser.
- Use simple, readable constraint expressions.
- Each constraint should be a complete boolean expression.
- Use OR clauses (lists of strings) when multiple alternative constraints are needed; an OR clause counts as a single top-level constraint.
- Example format:
  "x >= Date(2000,2,28)"
  "(x + Period(0,1,0)) > (y + Period(0,0,31))"
  "x == Date(2020,3,15)"
  "(x + Period(1,0,0)) < Date(2025,1,1)"
  "(x + Period(0,1,0) * 12) == (x + Period(1,0,0))"
  ["x >= Date(2000,2,28)", "x <= Date(2000,2,29)"]  # OR clause

OUTPUT REQUIREMENTS
- Output MUST be a valid JSON array of objects with the exact schema above.
- Each object must have "description", "constraints" (array of strings or mixed strings/lists for CNF), and "coverage_tags" (array of strings).
- Select appropriate coverage_tags from the CONTENT DIVERSITY section based on what each constraint set covers.
- No code fences, markdown, trailing commas, or comments.
- Use only ASCII quotes in JSON strings.
- Each constraint string must be parseable by the constraint parser.
- Use CNF format with OR clauses whenever multiple alternative constraints are needed, ensuring the OR usage target above is met."""


def _basic_schema_ok(items: Any) -> bool:
    """Validate that items is a list of constraint objects with required fields."""
    if not isinstance(items, list) or not items:
        return False

    # Check if it's a simple array of constraint strings (backward compatibility)
    if all(isinstance(item, str) for item in items):
        return True

    # Required fields for constraint objects (id is optional, added later)
    required_keys = {"description", "constraints", "coverage_tags"}
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
        # Validate constraint strings and OR clauses
        for clause in constraints:
            if isinstance(clause, str):
                continue
            if (
                isinstance(clause, list)
                and clause
                and all(isinstance(option, str) for option in clause)
            ):
                continue
            return False
        # Validate coverage tags
        if not all(isinstance(tag, str) for tag in it["coverage_tags"]):
            return False
    return True


def _normalize_to_dict_format(items: List[Any]) -> List[Dict]:
    """Normalize items to expected dict format with id, description, constraints, and coverage_tags.

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
                "constraints": [item],
                "coverage_tags": []
            })
        elif isinstance(item, dict):
            # Already in dict format, ensure it has an id
            constraint_dict = item.copy()
            if "id" not in constraint_dict:
                constraint_dict["id"] = str(get_next_id())
            result.append(constraint_dict)
        else:
            raise ValueError(f"Unexpected constraint format: {type(item)}")
    return result


def _count_constraints(constraints: List[Any]) -> int:
    """Count top-level constraints, treating OR clauses as single entries."""
    count = 0
    for clause in constraints:
        if isinstance(clause, str):
            count += 1
        elif isinstance(clause, list):
            count += 1
        else:
            # Should be filtered by _basic_schema_ok, but ignore silently here.
            continue
    return count


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
        exact_constraints_per_object: Optional[int] = None
    ) -> List[Dict]:
        """
        Generate DATE-SMT constraints with validation + simple auto-repair.
        Produces a mix of SAT/UNSAT across diverse boundary categories.

        Args:
            num_constraints: Number of constraint objects to generate
            retries: Number of retry attempts for failed generations
            batch_size: Batch size for generating large constraint sets
            tags: List of coverage tags to restrict generation to. If None, all tags are allowed (default).
                  Valid tags: leap_year, eom, year_vs_days, month_vs_days, chain_ops,
                  chain_ops_brackets, ineq_window, multi_var
            min_constraints_per_object: Minimum number of constraints per object (default: 1)
            max_constraints_per_object: Maximum number of constraints per object (default: 8)
            exact_constraints_per_object: Exact number of constraints per object (overrides min/max if set)
        """
        def _one_call(n: int) -> List[Dict]:
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
                else 1
            )
            max_c = (
                max_constraints_per_object
                if max_constraints_per_object is not None
                else 8
            )
            if exact_constraints_per_object is not None:
                constraint_count_instruction = (
                    f" CRITICAL: Each constraint object must have exactly {exact_constraints_per_object} constraints in its 'constraints' array. "
                    f"All {n} objects must have exactly {exact_constraints_per_object} constraints."
                )
            else:
                constraint_count_instruction = (
                    f" CRITICAL: Vary the number of constraints per object. Each constraint object must have between {min_c} and {max_c} constraints "
                    f"(inclusive) in its 'constraints' array. Treat each top-level entry as one constraint; an OR clause represented as a list counts as a single constraint toward this total. "
                    f"Generate a diverse mix - some objects should have {min_c} constraint(s), some should have {max_c} constraints, "
                    f"and others should have various counts in between. Do NOT make all objects have the same number of constraints."
                )

            local_prompt = (
                f"Generate exactly {n} unique constraint objects as a JSON array per the OUTPUT SCHEMA. "
                f"Each object must have 'description', 'constraints' (array of constraint strings), and 'coverage_tags' (array of tags).{constraint_count_instruction}{tag_restriction} "
                f"{'Ensure at least 5 distinct coverage_tags across the overall set. ' if not tags else ''}"
                f"Cover diverse edge cases (leap years, month boundaries, multi-variable relations, etc.). "
                f"Make each constraint set unique and different from the others."
            )
            for attempt in range(retries + 1):
                try:
                    local_raw = self.llm_client.call(SYSTEM_PROMPT, local_prompt)
                    items = self.llm_client.parse_json_response(local_raw, extract_array=True)
                    if not _basic_schema_ok(items):
                        raise ValueError("Output failed basic schema validation.")
                    for idx, it in enumerate(items, start=1):
                        constraint_total = _count_constraints(it["constraints"])
                        if exact_constraints_per_object is not None:
                            if constraint_total != exact_constraints_per_object:
                                raise ValueError(
                                    f"Constraint object {idx} has {constraint_total} constraints; expected exactly {exact_constraints_per_object}."
                                )
                        else:
                            if constraint_total < min_c or constraint_total > max_c:
                                raise ValueError(
                                    f"Constraint object {idx} has {constraint_total} constraints; expected between {min_c} and {max_c}."
                                )
                    return items
                except Exception as e:
                    local_last_err = e
                    try:
                        # Try to extract and parse JSON array as fallback
                        candidate = self.llm_client.parse_json_response(
                            local_raw if 'local_raw' in locals() else "", extract_array=True
                        )
                        if _basic_schema_ok(candidate):
                            return candidate
                    except Exception:
                        pass
            # Persist last failure context for this call
            try:
                debug_dir = os.path.join(os.getcwd(), "_debug")
                os.makedirs(debug_dir, exist_ok=True)
                with open(os.path.join(debug_dir, "last_raw.txt"), "w") as f:
                    f.write(local_raw)
                with open(os.path.join(debug_dir, "last_normalized.txt"), "w") as f:
                    f.write(local_norm if 'local_norm' in locals() else "")
            except Exception:
                pass
            raise RuntimeError(
                f"Batch generation failed after {retries+1} attempts: {local_last_err}"
            )

        if num_constraints <= batch_size:
            try:
                items = _one_call(num_constraints)
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
                batch_items = _one_call(take)
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
        help="Coverage tags to restrict generation to. Valid tags: leap_year, eom, year_vs_days, month_vs_days, chain_ops, chain_ops_brackets, ineq_window, multi_var. Default: all tags allowed",
    )
    parser.add_argument(
        "--min-constraints",
        type=int,
        help="Minimum number of constraints per constraint object (default: 1)",
    )
    parser.add_argument(
        "--max-constraints",
        type=int,
        help="Maximum number of constraints per constraint object (default: 8)",
    )
    parser.add_argument(
        "--exact-constraints",
        type=int,
        help="Exact number of constraints per constraint object (overrides min/max if set)",
    )
    args = parser.parse_args()

    generator = ConstraintGenerator(api_key=args.api_key, model=args.model, provider=args.provider)
    constraints = generator.generate_constraints(
        args.num,
        tags=args.tags,
        min_constraints_per_object=args.min_constraints,
        max_constraints_per_object=args.max_constraints,
        exact_constraints_per_object=args.exact_constraints
    )
    if constraints:
        generator.save_constraints(constraints, args.output)
        print(
            f"Successfully generated {len(constraints)} constraints using {generator.llm_client.provider.upper()}"
        )
    else:
        print("Failed to generate constraints")


if __name__ == "__main__":
    main()

