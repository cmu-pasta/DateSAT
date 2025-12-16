"""
Detection of candidate date/time constraints in Title 26.

By default, this script reads the parsed elements from:
    dataset/legal_doc_constraints/processed_data/parsed.jsonl
and writes candidate constraints to:
    dataset/legal_doc_constraints/processed_data/filtered.jsonl

Filtering logic:
- Records must contain temporal keywords/patterns (period keywords, relation keywords, 
  tax anchors, effective cues, or date patterns)
- Records must have MORE THAN the minimum number of unique matched patterns (default: 5)
- Configure the threshold with --min-patterns flag
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

# Import formatting function
from format_jsonl import format_as_pretty_jsonl

# Temporal period keywords
PERIOD_KEYWORDS = [
    r"\byear(s)?\b",
    r"\bmonth(s)?\b",
    r"\bday(s)?\b",
    r"\bperiod\b",
    r"\bweek(s)?\b",
    r"\bquarter(s)?\b",
    r"\bcalendar\s+quarter(s)?\b",
]

# Temporal relation keywords and constraint phrases
RELATION_KEYWORDS = [
    r"\bwithin\b",
    r"\bwithin\s+\d+\s+(calendar\s+)?(day|days|month|months|year|years)\b",
    r"\bwithin\s+(one|two|three|four|five|six|seven|eight|nine|ten|thirty)\s+(calendar\s+)?(day|days|month|months|year|years)\b",
    r"\bnot\s+later\s+than\b",
    r"\bno\s+later\s+than\b",
    r"\bnot\s+earlier\s+than\b",
    r"\bon\s+or\s+before\b",
    r"\bon\s+or\s+after\b",
    r"\bafter\b",
    r"\bbefore\b",
    r"\bprior\s+to\b",
    r"\bpreceding\b",
    r"\bbeginning\b",
    r"\bending\b",
    r"\bduring\b",
    r"\bbetween\b",
    r"\bfrom\b.*\bto\b",
    r"\bat\s+least\b",
    r"\bat\s+most\b",
    r"\bnot\s+more\s+than\b",
    r"\bnot\s+less\s+than\b",
    r"\bfor\s+a\s+period\s+of\s+\d+\s+(day|days|month|months|year|years)\b",
    r"\bfor\s+the\s+\d+[-\s]*(year|month|day)\s+period\b",
]

# Tax-specific temporal anchors/events and recurring patterns
TAX_ANCHORS = [
    r"\btaxable\s+year\b",
    r"\btaxable\s+years\b",
    r"\btaxable\s+period\b",
    r"\bcalendar\s+year\b",
    r"\bfiscal\s+year\b",
    r"\bplan\s+year\b",
    r"\bdate\s+of\s+filing\b",
    r"\bdate\s+of\s+payment\b",
    r"\bdue\s+date\b",
    r"\breturn\s+filing\b",
    r"\bfiling\s+date\b"
]

# Effective/applicability cues
EFFECTIVE_CUES = [
    r"\beffective\s+(on|after|for)\b",
    r"\bapplicable\s+to\b",
    r"\bfor\s+amounts\s+paid\s+or\s+incurred\s+after\b",
    r"\bfor\s+periods\s+beginning\s+after\b",
    r"\bbefore\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
    r"\bafter\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
]

# Date patterns (e.g., "15th day of the 4th month")
DATE_PATTERNS = [
    r"\b(the\s+)?\d+(st|nd|rd|th)\s+day\s+of\s+(the\s+)?\d+(st|nd|rd|th)\s+month\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",  # MM/DD/YYYY
    r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
]

# Combine all patterns
ALL_PATTERNS = (
    PERIOD_KEYWORDS
    + RELATION_KEYWORDS
    + TAX_ANCHORS
    + EFFECTIVE_CUES
    + DATE_PATTERNS
)

# Compile regex patterns (case-insensitive)
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in ALL_PATTERNS]


def detect_temporal_hits(text: str) -> Dict:
    """
    Detect temporal patterns in text and return matches.

    Returns a dict with:
    - temporal_hit: bool
    - matched_patterns: list of regex patterns that fired
    - matched_spans: list of {start, end, text}
    - trigger_phrases: unique list of matched span texts
    """
    hits: Dict = {
        "temporal_hit": False,
        "matched_patterns": [],
        "matched_spans": [],
        "trigger_phrases": [],
    }

    for pattern in COMPILED_PATTERNS:
        matches = pattern.finditer(text)
        for match in matches:
            hits["temporal_hit"] = True
            hits["matched_patterns"].append(pattern.pattern)
            span_text = match.group()
            hits["matched_spans"].append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "text": span_text,
                }
            )

    # Remove duplicate patterns while preserving order
    seen_patterns = set()
    unique_patterns: List[str] = []
    for pattern in hits["matched_patterns"]:
        if pattern not in seen_patterns:
            seen_patterns.add(pattern)
            unique_patterns.append(pattern)
    hits["matched_patterns"] = unique_patterns

    # Build unique trigger phrases from matched spans
    seen_triggers = set()
    trigger_phrases: List[str] = []
    for span in hits["matched_spans"]:
        t = span["text"]
        if t not in seen_triggers:
            seen_triggers.add(t)
            trigger_phrases.append(t)
    hits["trigger_phrases"] = trigger_phrases

    return hits


def is_temporal_clause(record: Dict) -> bool:
    """Determine if a record contains temporal logic."""
    text = record.get("text", "")
    if not text:
        return False

    # Check for temporal hits in the main text
    hits = detect_temporal_hits(text)

    # Filter out clauses that mention time-of-day or time zones (not date/period)
    exclusion_patterns = [
        r"\b(hour|minute|second|time\s+zone|DST|daylight\s+saving|standard\s+time)\b",
    ]
    for pattern in exclusion_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False

    return hits["temporal_hit"]


def main():
    parser = argparse.ArgumentParser(
        description="Detect candidate date/time constraints from parsed Title 26 elements"
    )
    parser.add_argument(
        "input_jsonl",
        type=str,
        nargs="?",
        help="Input JSONL file from parse.py "
        "(default: dataset/legal_doc_constraints/processed_data/parsed.jsonl)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSONL file path "
        "(default: dataset/legal_doc_constraints/processed_data/filtered.jsonl)",
    )
    parser.add_argument(
        "--min-patterns",
        type=int,
        default=5,
        help="Minimum number of unique matched patterns required to keep a record (default: 5)",
    )

    args = parser.parse_args()

    # Resolve default paths relative to the legal_doc_constraints package root
    root_dir = Path(__file__).resolve().parents[1]

    if args.input_jsonl:
        input_path = Path(args.input_jsonl)
    else:
        # Default parsed elements file from parse.py
        input_path = root_dir / "processed_data" / "parsed.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        # Default filtered candidates file
        output_path = root_dir / "processed_data" / "filtered.jsonl"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Detecting temporal clauses in {input_path}...")
    print(f"Output: {output_path}")
    print(f"Minimum unique matched patterns required: {args.min_patterns}")

    total = 0
    candidates = 0
    filtered_id = 0  # New sequential ID for filtered records

    with open(input_path, "r", encoding="utf-8") as f_in, \
         open(output_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            total += 1
            record = json.loads(line)

            if is_temporal_clause(record):
                # Preserve ALL fields from parsed record and add detection metadata
                text = record.get("text", "")
                hits = detect_temporal_hits(text)
                
                # Check if the number of unique matched patterns meets the threshold
                num_patterns = len(hits["matched_patterns"])
                if num_patterns <= args.min_patterns:
                    continue
                
                # Create output record preserving all original fields
                output_record = dict(record)  # Explicit copy to ensure all fields preserved
                
                # Save original parsed ID as parsed_id
                parsed_id = output_record.get("id")
                output_record["parsed_id"] = parsed_id
                
                # Add new sequential ID starting from 1
                filtered_id += 1
                output_record["id"] = str(filtered_id)
                
                # Add temporal detection metadata
                output_record["temporal_hit"] = True
                output_record["temporal_metadata"] = hits

                f_out.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                candidates += 1

    print(f"Done! Processed {total} records, found {candidates} temporal candidates.")
    print(f"Output saved to: {output_path}")
    print(f"Hit rate: {candidates/total*100:.2f}%" if total > 0 else "N/A")
    
    # Automatically generate formatted version
    formatted_output_path = output_path.parent / f"{output_path.stem}_formatted.jsonl"
    print(f"\nGenerating formatted version: {formatted_output_path}")
    format_as_pretty_jsonl(output_path, formatted_output_path)
    print(f"Formatted version saved to: {formatted_output_path}")


if __name__ == "__main__":
    main()
