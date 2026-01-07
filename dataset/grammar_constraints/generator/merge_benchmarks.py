#!/usr/bin/env python3
"""
Script to merge all JSON benchmark files from the benchmarks folder into a single file.
"""

import json
import os
from pathlib import Path


def merge_benchmarks():
    """
    Merges all JSON files from the benchmarks folder into a single constraints.json file.
    """
    # Get the directory paths
    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir.parent / "benchmarks"
    output_file = benchmarks_dir / "constraints.json"

    # Check if benchmarks directory exists
    if not benchmarks_dir.exists():
        print(f"Error: Benchmarks directory not found at {benchmarks_dir}")
        return

    # Find all JSON files in the benchmarks directory
    json_files = sorted(benchmarks_dir.glob("*.json"))

    # Exclude the output file if it already exists
    json_files = [f for f in json_files if f.name != "merged_benchmarks.json"]

    if not json_files:
        print(f"No JSON files found in {benchmarks_dir}")
        return

    print(f"Found {len(json_files)} JSON files to merge:")
    for f in json_files:
        print(f"  - {f.name}")

    # Merge all constraints
    merged_data = []

    for json_file in json_files:
        print(f"\nProcessing {json_file.name}...")
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            if not isinstance(data, list):
                print(f"  Warning: {json_file.name} does not contain a list. Skipping.")
                continue

            merged_data.extend(data)
            print(f"  Added {len(data)} constraints")

        except json.JSONDecodeError as e:
            print(f"  Error reading {json_file.name}: {e}")
            continue
        except Exception as e:
            print(f"  Unexpected error with {json_file.name}: {e}")
            continue

    # Write merged data to output file
    print(f"\nWriting merged data to {output_file}...")
    try:
        with open(output_file, "w") as f:
            json.dump(merged_data, f, indent=2)

        print(
            f"Successfully merged {len(merged_data)} total constraints into {output_file.name}"
        )

        # Print summary statistics
        print("\nSummary by category:")
        categories = {}
        for item in merged_data:
            item_id = item.get("id", "")
            # Extract category from ID (e.g., "grammar-sat-1" -> "sat")
            if "-" in item_id:
                parts = item_id.split("-")
                if len(parts) >= 2:
                    category = parts[1]
                    categories[category] = categories.get(category, 0) + 1

        for category, count in sorted(categories.items()):
            print(f"  {category}: {count} constraints")

    except Exception as e:
        print(f"Error writing output file: {e}")


if __name__ == "__main__":
    merge_benchmarks()
