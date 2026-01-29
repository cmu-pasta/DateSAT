"""
Randomly select a subset of constraints from filtered.jsonl.

By default, this script reads from:
    datesatbench/legal_doc_constraints/processed_data/filtered.jsonl
and writes to:
    datesatbench/legal_doc_constraints/processed_data/selected.jsonl

The script:
- Randomly selects N constraints (default: 200)
- Uses a fixed random seed for deterministic selection across runs
- Assigns new IDs in format "legal-1", "legal-2", etc.
- Preserves the original filtered ID as "filtered_id"
- Preserves all other fields from the filtered record

A formatted version is automatically generated at selected_formatted.jsonl.
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict

# Import formatting function
from format_jsonl import format_as_pretty_jsonl

# Fixed random seed for deterministic selection across runs
DEFAULT_RANDOM_SEED = 42


def load_records(input_path: Path) -> List[Dict]:
    """Load all records from a JSONL file."""
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Randomly select a subset of constraints from filtered.jsonl"
    )
    parser.add_argument(
        "input_jsonl",
        type=str,
        nargs="?",
        help="Input JSONL file from filter.py "
        "(default: datesatbench/legal_doc_constraints/processed_data/filtered.jsonl)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSONL file path "
        "(default: datesatbench/legal_doc_constraints/processed_data/selected.jsonl)",
    )
    parser.add_argument(
        "--num-samples",
        "-n",
        type=int,
        default=200,
        help="Number of constraints to randomly select (default: 200)",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed for deterministic selection (default: {DEFAULT_RANDOM_SEED})",
    )

    args = parser.parse_args()

    # Resolve default paths relative to the legal_doc_constraints package root
    root_dir = Path(__file__).resolve().parents[1]

    if args.input_jsonl:
        input_path = Path(args.input_jsonl)
    else:
        # Default filtered file from filter.py
        input_path = root_dir / "processed_data" / "filtered.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        # Default selected file
        output_path = root_dir / "processed_data" / "selected.jsonl"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading constraints from {input_path}...")
    
    # Load all records
    all_records = load_records(input_path)
    total_records = len(all_records)
    
    print(f"Total records available: {total_records}")
    
    # Determine actual sample size
    num_samples = min(args.num_samples, total_records)
    
    if num_samples < args.num_samples:
        print(f"Warning: Only {total_records} records available, selecting all of them")
    
    # Set random seed for deterministic selection
    random.seed(args.seed)
    
    # Randomly select records
    selected_records = random.sample(all_records, num_samples)
    
    print(f"Randomly selected {num_samples} constraints (seed={args.seed})")
    print(f"Output: {output_path}")

    # Write selected records with new IDs
    with open(output_path, "w", encoding="utf-8") as f_out:
        for idx, record in enumerate(selected_records, start=1):
            # Create output record preserving all fields
            output_record = dict(record)
            
            # Save original filtered ID as filtered_id
            filtered_id = output_record.get("id")
            output_record["filtered_id"] = filtered_id
            
            # Assign new ID in format "legal-1", "legal-2", etc.
            output_record["id"] = f"legal-{idx}"
            
            f_out.write(json.dumps(output_record, ensure_ascii=False) + "\n")

    print(f"\n=== SELECTION RESULTS ===")
    print(f"Total records in input: {total_records}")
    print(f"Records selected: {num_samples}")
    print(f"Random seed used: {args.seed}")
    print(f"Selection rate: {num_samples/total_records*100:.2f}%")
    print(f"=" * 50)
    print(f"\nOutput saved to: {output_path}")
    
    # Automatically generate formatted version
    formatted_output_path = output_path.parent / f"{output_path.stem}_formatted.jsonl"
    print(f"\nGenerating formatted version: {formatted_output_path}")
    format_as_pretty_jsonl(output_path, formatted_output_path)
    print(f"Formatted version saved to: {formatted_output_path}")


if __name__ == "__main__":
    main()
