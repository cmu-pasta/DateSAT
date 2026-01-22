#!/usr/bin/env python3
"""
Script to compute execution time statistics from benchmark result files.
"""

import argparse
import json
import statistics
from pathlib import Path


def load_execution_times(file_path):
    """Load execution times from a JSON result file."""
    with open(file_path, "r") as f:
        data = json.load(f)

    execution_times = []
    for entry in data:
        if "execution_time" in entry and entry["execution_time"] is not None:
            execution_times.append(entry["execution_time"])

    return execution_times


def compute_statistics(times):
    """Compute statistical measures for execution times."""
    if not times:
        return None

    times_sorted = sorted(times)
    n = len(times_sorted)

    stats = {
        "count": n,
        "mean": statistics.mean(times),
        "std_dev": statistics.stdev(times) if n > 1 else 0.0,
        "median": statistics.median(times),
        "percentile_25": times_sorted[int(n * 0.25)] if n > 0 else 0.0,
        "percentile_75": times_sorted[int(n * 0.75)] if n > 0 else 0.0,
    }

    return stats


def format_time(seconds):
    """Format time in milliseconds."""
    return f"{seconds * 1000:.2f} ms"


def print_statistics(stats):
    """Print statistics in a formatted way."""
    if stats is None:
        print("No execution time data found.")
        return

    print("\n" + "=" * 50)
    print("EXECUTION TIME STATISTICS")
    print("=" * 50)
    print(f"Total number of datapoints: {stats['count']}")
    print(f"25th percentile:            {format_time(stats['percentile_25'])}")
    print(f"Median:                     {format_time(stats['median'])}")
    print(f"75th percentile:            {format_time(stats['percentile_75'])}")
    print(f"Mean:                       {format_time(stats['mean'])}")
    print(f"Standard deviation:         {stats['std_dev']:.2f} s")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Compute execution time statistics from benchmark result files."
    )
    parser.add_argument("file_path", type=str, help="Path to the JSON result file")

    args = parser.parse_args()

    # Validate file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist.")
        return 1

    # Load and process data
    try:
        execution_times = load_execution_times(file_path)
        stats = compute_statistics(execution_times)
        print_statistics(stats)
        return 0
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
