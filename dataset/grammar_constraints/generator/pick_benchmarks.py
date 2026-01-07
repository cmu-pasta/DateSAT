import json
from pathlib import Path


def pick_benchmarks():
    """
    Parse naive_int.json results and create benchmark files.
    Picks constraints with 'sat' or 'unsat' status and places them
    in their respective json files in the constraints folder.
    """
    # Define paths
    results_file = Path(__file__).parent.parent / "results" / "naive_int.json"
    constraints_file = Path(__file__).parent.parent / "constraints" / "constraints.json"
    output_dir = Path(__file__).parent.parent / "constraints"

    # Read the results file
    print(f"Reading results from: {results_file}")
    with open(results_file, "r") as f:
        results = json.load(f)

    # Read the constraints file
    print(f"Reading constraints from: {constraints_file}")
    with open(constraints_file, "r") as f:
        constraints_data = json.load(f)

    # Create a dictionary for quick lookup by id
    constraints_dict = {item["id"]: item for item in constraints_data}

    # Categorize by status
    sat_items = []
    unsat_items = []
    timeout_items = []

    for result in results:
        constraint_id = result["id"]
        status = result["status"]
        execution_time = result.get("execution_time", 0)

        # Get the corresponding constraint from constraints.json
        if constraint_id in constraints_dict:
            constraint_item = constraints_dict[constraint_id].copy()

            # Add execution time to the constraint item
            constraint_item["execution_time"] = execution_time

            # Add to appropriate list based on status
            if status == "sat":
                sat_items.append(constraint_item)
            elif status == "unsat":
                unsat_items.append(constraint_item)
            elif status == "timeout":
                timeout_items.append(constraint_item)
        else:
            print(f"Warning: Constraint {constraint_id} not found in constraints.json")

    # Sort by execution time in descending order and update IDs
    sat_items.sort(key=lambda x: x["execution_time"], reverse=True)
    for i, item in enumerate(sat_items, start=1):
        item["id"] = f"grammar-sat-{i}"

    unsat_items.sort(key=lambda x: x["execution_time"], reverse=True)
    for i, item in enumerate(unsat_items, start=1):
        item["id"] = f"grammar-unsat-{i}"

    timeout_items.sort(key=lambda x: x["execution_time"], reverse=True)
    for i, item in enumerate(timeout_items, start=1):
        item["id"] = f"grammar-timeout-{i}"

    # Define output files
    sat_file = output_dir / "sat_constraints.json"
    unsat_file = output_dir / "unsat_constraints.json"
    timeout_file = output_dir / "timeout_constraints.json"

    # Helper function to load existing constraints and append new ones
    def append_unique_constraints(file_path, new_items, status_name):
        existing_items = []

        # Load existing constraints if file exists
        if file_path.exists():
            print(f"\nLoading existing {status_name} constraints from: {file_path}")
            with open(file_path, "r") as f:
                try:
                    existing_items = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse existing file, starting fresh")
                    existing_items = []

        # Create a set of existing constraints for duplicate checking
        # Only check the "constraints" field for exact match
        existing_constraints_set = {
            json.dumps(item.get("constraints", []), sort_keys=True)
            for item in existing_items
        }

        # Filter out duplicates
        unique_new_items = []
        duplicate_count = 0
        for item in new_items:
            constraints_json = json.dumps(item.get("constraints", []), sort_keys=True)
            if constraints_json not in existing_constraints_set:
                unique_new_items.append(item)
                existing_constraints_set.add(constraints_json)
            else:
                duplicate_count += 1

        # Append unique items to existing list
        combined_items = existing_items + unique_new_items

        # Sort combined list by execution time in descending order
        combined_items.sort(key=lambda x: x.get("execution_time", 0), reverse=True)

        # Renumber IDs based on sorted order
        for i, item in enumerate(combined_items, start=1):
            item["id"] = f"grammar-{status_name.lower()}-{i}"

        # Write combined list back to file
        print(f"Writing to {file_path}:")
        print(f"  - Existing: {len(existing_items)}")
        print(f"  - New unique: {len(unique_new_items)}")
        print(f"  - Duplicates skipped: {duplicate_count}")
        print(f"  - Total: {len(combined_items)}")

        with open(file_path, "w") as f:
            json.dump(combined_items, f, indent=2)

        return len(unique_new_items), duplicate_count

    # Append sat constraints
    sat_new, sat_dups = append_unique_constraints(sat_file, sat_items, "SAT")

    # Append unsat constraints
    unsat_new, unsat_dups = append_unique_constraints(unsat_file, unsat_items, "UNSAT")

    # Append timeout constraints
    timeout_new, timeout_dups = append_unique_constraints(
        timeout_file, timeout_items, "TIMEOUT"
    )

    # Print summary
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Total results processed: {len(results)}")
    print(
        f"  SAT constraints found: {len(sat_items)} (new: {sat_new}, duplicates: {sat_dups})"
    )
    print(
        f"  UNSAT constraints found: {len(unsat_items)} (new: {unsat_new}, duplicates: {unsat_dups})"
    )
    print(
        f"  TIMEOUT constraints found: {len(timeout_items)} (new: {timeout_new}, duplicates: {timeout_dups})"
    )
    print("=" * 50)


if __name__ == "__main__":
    pick_benchmarks()
