"""
Enhanced LLM client for generating DATE-SMT constraints.

Supports both OpenAI and Anthropic APIs with robust JSON parsing and coverage-oriented generation.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
try:
    from .id_counter import get_next_id
except ImportError:
    from id_counter import get_next_id

# Default models for each provider
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet-latest"

SYSTEM_PROMPT = """You are an expert DATE-SMT constraint author.

GOAL
Produce a JSON array of N constraint objects that exercise a Python DATE-SMT library.

SCOPE & OPERATIONS (very important)
- Use ONLY dates and calendar periods (no times of day, no time zones, no DST).
- Stay within Gregorian date range where simple leap-year rules are valid: 1900-03-01 to 2100-02-28.
- Allowed operations:
  • Date ± Period → Date
  • Period ± Period → Period
  • Period × Int → Period
  • Date ▷◁ Date (▷◁ ∈ {==, !=, <, <=, >, >=})
- STRICTLY FORBIDDEN: Period comparisons (Period ▷◁ Period). Period comparison is undefined in all contexts.
- FORBIDDEN EXAMPLES: Period(0,1,0) > Period(0,0,31), p > q, Period(1,0,0) == Period(0,12,0)
- Instead, compare dates after adding periods: (x + Period(0,1,0)) > (x + Period(0,0,31))

LIBRARY SEMANTICS (AVAILABLE IN THE TEST HARNESS)
- Constructors: Date(y, m, d), Period(years, months, days)
- Builder: DateSMTBuilder(approach?)  # approach will be injected by harness
- Variables:
  • You MAY use predeclared names x, y, z (dates) and p, q, r (periods) directly, or create fresh via builder.add_*_var.
  • Valid ranges: 1900-03-01 <= Date <= 2100-02-28.
SUPPORTED OPERATIONS (engine-compatible):
  • Date + Period → Date (concrete Period(...))
  • Date + PeriodVar → Date (now supported)
  • Period + Period → Period (use chained concrete Period(...) arithmetic only)
  • Date ▷◁ Date where ▷◁ ∈ {==, !=, <, <=, >, >=}
  • DO NOT: compare Period ▷◁ Period (unsupported)
  • DO NOT: compare Period ▷◁ Period (unsupported)
  • DO NOT: multiply Period or PeriodVar (currently unsupported)
- Builder API (always use via a local variable named builder):
  • builder = DateSMTBuilder("advanced" or "baseline")  # already provided in harness
  • builder.add_date_var(name: str) -> Date-like symbolic var
  • builder.add_period_var(name: str) -> Period-like symbolic var (avoid adding to Date)
  • builder.add_constraint(z3_bool_expr, description: str = "")
  • result = builder  # end your snippet with this
- Tips for robust code snippets inside JSON strings:
  • Prefer single quotes in Python snippets to minimize JSON escaping.
  • Encode newlines as \n in the JSON string.
  • Avoid printing or IO; just build constraints.

CONTENT REQUIREMENTS
- Cover diverse edge cases:
  1) Leap year boundaries (e.g., Feb 28/29)
  2) End-of-month rollovers (30 vs 31 vs 28/29)
  3) Year-vs-day contrasts (1 year vs 365/366 days)
  4) Month-vs-day contrasts (e.g., +1 month vs +31 days)
  5) Chains of additions/subtractions (normalize months, carry days)
  6) Inequality windows (prove UNSAT via tight ranges; ensure SAT via wide ranges)
  7) Multi-variable relations (link x, y, z with different periods)
- Mix of satisfiable and unsatisfiable instances (aim ~70% SAT).
- Use realistic ranges (prefer 1990–2040 unless an edge case needs otherwise, but never outside 1900-03-01..2100-02-28).

OUTPUT SCHEMA (STRICT)
Return ONLY a JSON array (no markdown fences, no commentary).
Each element must be an object:
{
  "id": "string-unique",
  "description": "brief human explanation",
  "constraint_code": "Python code string to build/assert the constraint(s)",
  "variables": ["list", "of", "used", "names"],
  "coverage_tags": ["leap_boundary","eom","year_vs_days","month_vs_days","chain_add","ineq_window","multi_var"]
}

STYLE FOR constraint_code
- Build with DateSMTBuilder(); declare or reuse x,y,z,p,q,r; then assert constraints.
- Prefer small, readable snippets; avoid random() or environment calls.
- No printing; just build constraints. Example skeleton:

builder = DateSMTBuilder()
x = builder.add_date_var("x")
y = builder.add_date_var("y")
# ... your constraints ...
builder.add_constraint(x + Period(1,2,0) > y)
result = builder  # implicit: harness will solve

VALIDATION GUARDRAILS
- Ensure all dates are within 1900-03-01..2100-02-28.
- Never assume Period equality or compare two Periods.
- Ensure month and day values are 1-based and valid (1<=m<=12, 1<=d<=31).

FINAL INSTRUCTIONS
- Output MUST be a single JSON array with the exact schema above.
- No code fences. No prose. No trailing commas. No comments.
- Inside JSON strings, use ONLY plain ASCII quotes. Prefer single quotes in Python snippets (e.g., add_date_var('x')).
- Ensure any newlines inside constraint_code are encoded as \n in the JSON string, not raw line breaks.
- Do not include backticks, markdown, or explanations before/after the JSON."""


def _basic_schema_ok(items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False
    required_keys = {
        "id",
        "description",
        "constraint_code",
        "variables",
        "coverage_tags",
        "expected_satisfiable",
    }
    for it in items:
        if not isinstance(it, dict):
            return False
        if set(it.keys()) != required_keys:
            return False
        if not isinstance(it["id"], str):
            return False
        if not isinstance(it["description"], str):
            return False
        if not isinstance(it["constraint_code"], str):
            return False
        if not isinstance(it["variables"], list):
            return False
        if not isinstance(it["coverage_tags"], list):
            return False
        if not isinstance(it["expected_satisfiable"], bool):
            return False
    return True


def _strip_code_fences(s: str) -> str:
    # Handle ```json ... ``` or ``` ... ``` blocks gracefully.
    if "```" not in s:
        return s.strip()
    # Prefer explicitly tagged json fence
    m = re.search(r"```json\s*(.*?)```", s, flags=re.S)
    if m:
        return m.group(1).strip()
    # Fallback: first fenced block
    m = re.search(r"```(.*?)```", s, flags=re.S)
    return m.group(1).strip() if m else s.strip()


def _normalize_llm_json(s: str) -> str:
    """Best-effort normalization to improve JSON parse success without altering content semantics.

    - Strip BOM/whitespace
    - Replace curly/smart quotes with ASCII quotes
    - Normalize line endings
    - Ensure backticks are removed
    """
    if not isinstance(s, str):
        return s
    txt = s.strip().lstrip("\ufeff")
    # Remove stray backtick fences if any slipped through
    txt = txt.replace("```", "")
    # Normalize fancy quotes to plain quotes
    smart_double = "\u201c\u201d\uFF02"
    smart_single = "\u2018\u2019\uFF07"
    for ch in smart_double:
        txt = txt.replace(ch, '"')
    for ch in smart_single:
        txt = txt.replace(ch, "'")
    # Normalize line endings
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    return txt


def _add_sequential_ids(constraints: List[Dict]) -> List[Dict]:
    """Add sequential IDs to constraints using global counter."""
    result = []
    for constraint in constraints:
        constraint_with_id = constraint.copy()
        constraint_with_id["id"] = str(get_next_id())
        result.append(constraint_with_id)
    return result


def list_saved_constraints(directory: str = ".") -> List[str]:
    """List all saved constraint files in a directory."""
    import glob

    # Look for any JSON files that might contain constraints
    patterns = ["*constraints*.json", "*constraint*.json", "*.json"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(directory, pattern)))
    return sorted(list(set(files)))


def _detect_provider_and_model() -> tuple[str, str]:
    """Auto-detect provider and return appropriate model."""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if anthropic_key and not openai_key:
        return "anthropic", DEFAULT_ANTHROPIC_MODEL
    elif openai_key and not anthropic_key:
        return "openai", DEFAULT_OPENAI_MODEL
    elif anthropic_key and openai_key:
        # Both available, prefer Anthropic
        return "anthropic", DEFAULT_ANTHROPIC_MODEL
    else:
        raise ValueError(
            "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable, or pass api_key parameter."
        )


class LLMClient:
    """Enhanced DATE-SMT constraint generator supporting OpenAI and Anthropic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
    ):
        self.api_key = api_key
        self.provider = provider.lower()

        # Auto-detect provider and model if not specified
        if self.provider == "auto":
            self.provider, default_model = _detect_provider_and_model()
            self.model = model or default_model
        else:
            # Provider explicitly specified
            if self.provider == "openai":
                self.api_key = api_key or os.getenv("OPENAI_API_KEY")
                if not self.api_key:
                    raise ValueError(
                        "OpenAI API key required. Set OPENAI_API_KEY or pass api_key."
                    )
                self.model = model or DEFAULT_OPENAI_MODEL
            elif self.provider == "anthropic":
                self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
                if not self.api_key:
                    raise ValueError(
                        "Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key."
                    )
                self.model = model or DEFAULT_ANTHROPIC_MODEL
            else:
                raise ValueError(
                    f"Unsupported provider: {provider}. Use 'openai', 'anthropic', or 'auto'."
                )

        # Set up the appropriate client
        if self.provider == "openai":
            import openai

            self.client = openai.OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)

        # Light defaults that usually help JSON fidelity
        self.max_tokens = 2000
        self.temperature = 0.4
        self.top_p = 0.95

    def _ask(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider == "openai":
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "system",
                        "content": "When randomness is needed, use a deterministic seed of 1337.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
            )
            return resp.choices[0].message.content
        elif self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt
                + "\n\nWhen randomness is needed, use a deterministic seed of 1337.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            return resp.content[0].text

    def generate_constraints(
        self, num_constraints: int = 8, retries: int = 2, batch_size: int = 5
    ) -> List[Dict]:
        """
        Generate DATE-SMT constraints with validation + simple auto-repair.
        Produces a mix of SAT/UNSAT across diverse boundary categories.
        """
        def _one_call(n: int) -> List[Dict]:
            local_last_err = None
            local_raw = ""
            local_norm = ""
            local_prompt = (
                f"Produce exactly {n} constraint objects as a SINGLE JSON array per the schema. "
                f"Ensure at least 5 distinct coverage_tags across the overall set; keep descriptions concise. "
                f"Make each constraint unique and different from the others."
            )
            for attempt in range(retries + 1):
                try:
                    local_raw = self._ask(SYSTEM_PROMPT, local_prompt)
                    txt = _strip_code_fences(local_raw)
                    local_norm = _normalize_llm_json(txt)
                    items = json.loads(local_norm)
                    if not _basic_schema_ok(items):
                        raise ValueError("Output failed basic schema validation.")
                    return items
                except Exception as e:
                    local_last_err = e
                    try:
                        candidate = self._extract_json_array(local_raw if 'local_raw' in locals() else "")
                        candidate = _normalize_llm_json(candidate)
                        items = json.loads(candidate)
                        if _basic_schema_ok(items):
                            return items
                    except Exception:
                        pass
            # Persist last failure context for this call
            try:
                debug_dir = os.path.join(os.getcwd(), "_debug")
                os.makedirs(debug_dir, exist_ok=True)
                with open(os.path.join(debug_dir, "last_raw.txt"), "w") as f:
                    f.write(local_raw)
                with open(os.path.join(debug_dir, "last_normalized.txt"), "w") as f:
                    f.write(local_norm)
            except Exception:
                pass
            raise RuntimeError(f"Batch generation failed after {retries+1} attempts: {local_last_err}")

        if num_constraints <= batch_size:
            try:
                items = _one_call(num_constraints)
                return _add_sequential_ids(items)
            except Exception as e:
                print(f"[generate_constraints] Failed: {e}")
                return []

        # Batched path
        remaining = num_constraints
        all_items: List[Dict] = []
        while remaining > 0:
            take = min(batch_size, remaining)
            try:
                batch_items = _one_call(take)
                all_items.extend(batch_items)
                remaining -= take
            except Exception as e:
                print(f"[generate_constraints] Batch failed (requested {take}): {e}")
                return []
        return _add_sequential_ids(all_items)

    @staticmethod
    def _extract_json_array(s: str) -> str:
        """
        Greedy substring extraction of the first plausible JSON array.
        """
        start = s.find('[')
        end = s.rfind(']')
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
        raise ValueError("No JSON array found in response.")

    @staticmethod
    def save_constraints(constraints: List[Dict], filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(constraints, f, indent=2)
        print(f"Saved {len(constraints)} constraints to {filename}")

    @staticmethod
    def load_constraints(filename: str) -> List[Dict]:
        """Load constraints from a JSON file."""
        with open(filename, 'r') as f:
            return json.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate DATE-SMT constraints with LLM"
    )
    parser.add_argument(
        "--num", type=int, default=8, help="Number of constraints to generate"
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
        "--list", action="store_true", help="List saved constraint files"
    )
    args = parser.parse_args()

    if args.list:
        files = list_saved_constraints()
        if files:
            print("Saved constraint files:")
            for file in files:
                print(f"  📄 {file}")
        else:
            print("No constraint files found")
        return

    client = LLMClient(api_key=args.api_key, model=args.model, provider=args.provider)
    constraints = client.generate_constraints(args.num)
    if constraints:
        client.save_constraints(constraints, args.output)
        print(
            f"Successfully generated {len(constraints)} constraints using {client.provider.upper()}"
        )
    else:
        print("Failed to generate constraints")


if __name__ == "__main__":
    main()
