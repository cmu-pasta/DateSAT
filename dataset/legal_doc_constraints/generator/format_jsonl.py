"""
Format JSONL files for better readability.

Converts compact JSONL (one JSON object per line) into a more readable format:
- Option 1: Pretty-printed JSON (one object per line, but formatted)
- Option 2: Pretty-printed JSON array (all objects in one array)
- Option 3: Human-readable text summary
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def format_as_pretty_jsonl(input_path: Path, output_path: Path):
    """Format each line as pretty-printed JSON."""
    print(f"Formatting {input_path} as pretty JSONL...")

    with open(input_path, "r", encoding="utf-8") as f_in, \
         open(output_path, "w", encoding="utf-8") as f_out:

        count = 0
        for line in f_in:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                pretty_json = json.dumps(obj, indent=2, ensure_ascii=False)
                f_out.write(pretty_json + "\n\n")
                count += 1
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON on line {count + 1}: {e}")
                continue

    print(f"Formatted {count} objects to {output_path}")


def format_as_json_array(input_path: Path, output_path: Path):
    """Format as a single JSON array with pretty printing."""
    print(f"Formatting {input_path} as JSON array...")

    objects = []
    with open(input_path, "r", encoding="utf-8") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                objects.append(obj)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON: {e}")
                continue

    with open(output_path, "w", encoding="utf-8") as f_out:
        json.dump(objects, f_out, indent=2, ensure_ascii=False)

    print(f"Formatted {len(objects)} objects to {output_path}")


def format_as_text_summary(input_path: Path, output_path: Path, max_items: int = None):
    """Format as human-readable text summary."""
    print(f"Formatting {input_path} as text summary...")

    with open(input_path, "r", encoding="utf-8") as f_in, \
         open(output_path, "w", encoding="utf-8") as f_out:

        count = 0
        for line in f_in:
            if max_items and count >= max_items:
                break

            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                count += 1

                # Write summary
                f_out.write(f"{'=' * 80}\n")
                f_out.write(f"Constraint #{count}\n")
                f_out.write(f"{'=' * 80}\n\n")

                f_out.write(f"ID: {obj.get('id', 'N/A')}\n")
                f_out.write(f"Description: {obj.get('description', 'N/A')[:200]}...\n\n")

                constraints = obj.get('constraints', [])
                f_out.write(f"Constraints ({len(constraints)}):\n")
                for i, constraint in enumerate(constraints, 1):
                    if isinstance(constraint, list):
                        # OR clause
                        f_out.write(f"  {i}. OR clause:\n")
                        for j, or_constraint in enumerate(constraint, 1):
                            f_out.write(f"     {j}. {or_constraint}\n")
                    else:
                        f_out.write(f"  {i}. {constraint}\n")

                tags = obj.get('coverage_tags', [])
                if tags:
                    f_out.write(f"\nCoverage Tags: {', '.join(tags)}\n")

                provenance = obj.get('provenance', {})
                if provenance:
                    f_out.write(f"\nProvenance:\n")
                    usc_ref = provenance.get('usc_ref', {})
                    if usc_ref:
                        f_out.write(f"  USC Title: {usc_ref.get('title', 'N/A')}\n")
                        f_out.write(f"  USC Section: {usc_ref.get('section', 'N/A')}\n")
                    heading = provenance.get('heading')
                    if heading:
                        f_out.write(f"  Heading: {heading}\n")

                # Truncated original text
                original_text = provenance.get('original_text', '')
                if original_text:
                    truncated = original_text[:500] + "..." if len(original_text) > 500 else original_text
                    f_out.write(f"\nOriginal Text (truncated):\n{truncated}\n")

                f_out.write("\n\n")

            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON on line {count + 1}: {e}")
                continue

    print(f"Formatted {count} objects to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Format JSONL files for better readability"
    )
    parser.add_argument(
        "input_jsonl",
        type=str,
        help="Input JSONL file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file (default: input file with .formatted extension)",
    )
    parser.add_argument(
        "--format",
        choices=["pretty", "array", "text"],
        default="pretty",
        help="Output format: 'pretty' (pretty JSONL), 'array' (JSON array), or 'text' (human-readable summary)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum items to format (for text format, useful for preview)",
    )

    args = parser.parse_args()

    input_path = Path(args.input_jsonl)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        if args.format == "pretty":
            output_path = input_path.with_suffix(".pretty.jsonl")
        elif args.format == "array":
            output_path = input_path.with_suffix(".json")
        else:  # text
            output_path = input_path.with_suffix(".txt")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Format based on choice
    if args.format == "pretty":
        format_as_pretty_jsonl(input_path, output_path)
    elif args.format == "array":
        format_as_json_array(input_path, output_path)
    else:  # text
        format_as_text_summary(input_path, output_path, max_items=args.max_items)

    print(f"\nDone! Output saved to: {output_path}")


if __name__ == "__main__":
    main()
