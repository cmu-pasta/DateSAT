#!/usr/bin/env python3
"""
Combine all constraint JSON files from the constraints folder into a single file.

This script reads all JSON files in the constraints folder (excluding constraints.json),
combines all constraints into one array, and saves the result as constraints.json.
"""

import json
import os
from pathlib import Path
from typing import List, Dict


def _resolve_existing_dir(path_str: str, script_dir: Path) -> Path:
    """Resolve a directory path, considering several relative bases."""
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate

    parent_dir = script_dir.parent
    for base in (Path.cwd(), script_dir, parent_dir):
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    # Fall back to assuming path relative to script_dir even if it doesn't exist,
    # so the caller still sees a helpful error message.
    return (script_dir / candidate).resolve()


def _resolve_output_path(path_str: str, script_dir: Path) -> Path:
    """Resolve an output path, allowing directories that don't exist yet."""
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate

    parent_dir = script_dir.parent
    for base in (Path.cwd(), script_dir, parent_dir):
        resolved = (base / candidate).resolve()
        if resolved.parent.exists():
            return resolved
    return (script_dir / candidate).resolve()


def combine_constraints(
    constraints_dir: str = "constraints", output_file: str = "constraints/constraints.json"
) -> None:
    """
    Combine all constraint files from the constraints directory into one file.
    
    Args:
        constraints_dir: Directory containing constraint JSON files
        output_file: Output file path for combined constraints
    """
    # Get the script directory to resolve paths relative to it
    script_dir = Path(__file__).parent.resolve()
    constraints_path = _resolve_existing_dir(constraints_dir, script_dir)
    
    if not constraints_path.exists():
        print(f"Error: Constraints directory '{constraints_dir}' does not exist")
        return
    
    # Find all JSON files in the constraints directory, excluding constraints.json
    json_files = sorted(constraints_path.glob("*.json"))
    json_files = [f for f in json_files if f.name != "constraints.json"]
    
    if not json_files:
        print(f"No constraint files found in '{constraints_dir}' (excluding constraints.json)")
        return
    
    print(f"Found {len(json_files)} constraint file(s) to combine:")
    for f in json_files:
        print(f"  - {f.name}")
    
    # Load, re-id, and combine all constraints
    all_constraints: List[Dict] = []
    total_constraints = 0
    next_id = 1  # Continuous counter across files, in alphabetical file order
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
                
            if not isinstance(constraints, list):
                print(f"Warning: {json_file.name} is not a JSON array, skipping")
                continue

            base_name = json_file.stem  # e.g., logical_operators from logical_operators.json

            for c in constraints:
                # Only process dict-style constraint objects
                if not isinstance(c, dict):
                    continue

                # Preserve original id (if any) as generated_id
                if "id" in c:
                    c["generated_id"] = c["id"]

                # Assign new continuous id: llm-FILENAME-NUM
                c["id"] = f"llm-{base_name}-{next_id}"
                next_id += 1
            
            all_constraints.extend(constraints)
            total_constraints += len(constraints)
            print(f"  Loaded {len(constraints)} constraints from {json_file.name}")
            
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse {json_file.name}: {e}")
            continue
        except Exception as e:
            print(f"Error: Failed to read {json_file.name}: {e}")
            continue
    
    if not all_constraints:
        print("No constraints found to combine")
        return
    
    # Save combined constraints
    output_path = _resolve_output_path(output_file, script_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_constraints, f, indent=2)
    
    print(f"\nSuccessfully combined {total_constraints} constraints from {len(json_files)} file(s)")
    print(f"Saved to: {output_path}")


def main():
    """Main function with command-line argument support."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Combine all constraint JSON files into constraints.json"
    )
    parser.add_argument(
        "--constraints-dir",
        default="constraints",
        help="Directory containing constraint JSON files (default: constraints)"
    )
    parser.add_argument(
        "--output",
        default="constraints/constraints.json",
        help="Output file path (default: constraints/constraints.json)"
    )
    
    args = parser.parse_args()
    
    combine_constraints(args.constraints_dir, args.output)


if __name__ == "__main__":
    main()

