#!/usr/bin/env python3
"""
Script to compute overall solve percentage and solve time statistics
across all benchmarks and encodings.

Benchmarks:
- llm_constraints
- grammar_constraints
- legal_doc_constraints

Encodings:
- simple_int.json
- epoch_days_int.json
- hybrid_int.json
- alpha_beta_int.json
- alpha_beta_table_int.json

Total: 450 constraints * 5 encodings = 2250 entries
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

# Configuration
BENCHMARKS = [
    "llm_constraints",
    "grammar_constraints",
    "legal_doc_constraints",
]

ENCODINGS = [
    "simple_int.json",
    "epoch_days_int.json",
    "hybrid_int.json",
    "alpha_beta_int.json",
    "alpha_beta_table_int.json",
]

ENCODING_NAMES = {
    "simple_int.json": "Simple",
    "epoch_days_int.json": "Epoch Days",
    "hybrid_int.json": "Hybrid",
    "alpha_beta_int.json": "Alpha-Beta",
    "alpha_beta_table_int.json": "Alpha-Beta Table",
}

BENCHMARK_NAMES = {
    "llm_constraints": "LLM",
    "grammar_constraints": "Grammar",
    "legal_doc_constraints": "Legal Doc",
}


def load_results(file_path):
    """Load results from a JSON file."""
    with open(file_path, "r") as f:
        return json.load(f)


def is_solved(entry):
    """Check if a constraint was solved (sat or unsat, not timeout/error)."""
    return entry.get("status") in ("sat", "unsat")


def get_execution_time(entry):
    """Get execution time from an entry, returning None if not available."""
    time = entry.get("execution_time")
    if time is not None and is_solved(entry):
        return time
    return None


def format_time(seconds, unit="ms"):
    """Format time in the specified unit (ms or s)."""
    if seconds is None:
        return "N/A"
    if unit == "ms":
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.4f} s"


def compute_time_stats(times):
    """Compute statistical measures for execution times."""
    if not times:
        return None

    times_sorted = sorted(times)
    n = len(times_sorted)

    return {
        "count": n,
        "mean": statistics.mean(times),
        "std_dev": statistics.stdev(times) if n > 1 else 0.0,
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "total": sum(times),
        "percentile_25": times_sorted[int(n * 0.25)] if n > 0 else 0.0,
        "percentile_75": times_sorted[int(n * 0.75)] if n > 0 else 0.0,
        "percentile_95": times_sorted[int(n * 0.95)] if n > 0 else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compute overall solve percentage and solve time statistics."
    )
    parser.add_argument(
        "--datesatbench-dir",
        type=str,
        default=None,
        help="Path to the datesatbench directory (default: auto-detect)",
    )
    parser.add_argument(
        "--unit",
        "-u",
        type=str,
        choices=["ms", "s"],
        default="ms",
        help="Time unit for output: 'ms' (milliseconds) or 's' (seconds). Default: ms",
    )
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed breakdown by benchmark and encoding",
    )

    args = parser.parse_args()

    # Determine datesatbench directory
    if args.datesatbench_dir:
        datesatbench_dir = Path(args.datesatbench_dir)
    else:
        # Auto-detect: script is in datesatbench/utils/
        script_dir = Path(__file__).parent
        datesatbench_dir = script_dir.parent

    # Validate datesatbench directory
    if not datesatbench_dir.exists():
        print(f"Error: Dataset directory '{datesatbench_dir}' does not exist.")
        return 1

    # Collect all results
    all_entries = []
    stats_by_benchmark = defaultdict(list)
    stats_by_encoding = defaultdict(list)
    stats_by_both = defaultdict(list)

    missing_files = []

    for benchmark in BENCHMARKS:
        for encoding in ENCODINGS:
            results_dir = datesatbench_dir / benchmark / "results"

            # Collect from run_N subdirectories if they exist, else fall back to flat file
            run_dirs = (
                sorted(
                    [
                        d
                        for d in results_dir.iterdir()
                        if d.is_dir() and d.name.startswith("run_")
                    ],
                    key=lambda d: int(d.name.split("_")[1]),
                )
                if results_dir.exists()
                else []
            )

            if run_dirs:
                sources = [d / encoding for d in run_dirs]
            else:
                sources = [results_dir / encoding]

            found_any = False
            for file_path in sources:
                if not file_path.exists():
                    missing_files.append(str(file_path))
                    continue
                try:
                    results = load_results(file_path)
                    run_name = file_path.parent.name if run_dirs else None
                    for entry in results:
                        entry["_benchmark"] = benchmark
                        entry["_encoding"] = encoding
                        if run_name:
                            entry["_run"] = run_name
                        all_entries.append(entry)
                        stats_by_benchmark[benchmark].append(entry)
                        stats_by_encoding[encoding].append(entry)
                        stats_by_both[(benchmark, encoding)].append(entry)
                    found_any = True
                except Exception as e:
                    print(f"Warning: Failed to load {file_path}: {e}")

            if not found_any and not run_dirs:
                missing_files.append(str(results_dir / encoding))

    if missing_files:
        print(f"\nWarning: {len(missing_files)} result files not found:")
        for f in missing_files[:5]:
            print(f"  - {f}")
        if len(missing_files) > 5:
            print(f"  ... and {len(missing_files) - 5} more")
        print()

    if not all_entries:
        print("Error: No result data found.")
        return 1

    # Compute overall statistics
    total_entries = len(all_entries)
    solved_entries = [e for e in all_entries if is_solved(e)]
    unsolved_entries = [e for e in all_entries if not is_solved(e)]

    solved_count = len(solved_entries)
    unsolved_count = len(unsolved_entries)
    solve_rate = (solved_count / total_entries) * 100 if total_entries > 0 else 0

    # Get execution times for solved entries
    execution_times = [get_execution_time(e) for e in solved_entries]
    execution_times = [t for t in execution_times if t is not None]
    time_stats = compute_time_stats(execution_times)

    # Count by status
    status_counts = defaultdict(int)
    for entry in all_entries:
        status_counts[entry.get("status", "unknown")] += 1

    # Print overall summary
    print("\n" + "=" * 70)
    print("OVERALL BENCHMARK STATISTICS")
    print("=" * 70)
    print(f"\nBenchmarks: {', '.join(BENCHMARK_NAMES.values())}")
    print(f"Encodings:  {', '.join(ENCODING_NAMES.values())}")
    print()
    print("-" * 70)
    print("SOLVE STATISTICS")
    print("-" * 70)
    print(f"Total entries:     {total_entries:,}")
    print(f"Solved (SAT/UNSAT):{solved_count:,}")
    print(f"Unsolved (timeout):{unsolved_count:,}")
    print(f"Solve rate:        {solve_rate:.2f}%")
    print()
    print("Status breakdown:")
    for status, count in sorted(status_counts.items()):
        pct = (count / total_entries) * 100
        print(f"  {status:12s}: {count:5,} ({pct:5.2f}%)")

    if time_stats:
        print()
        print("-" * 70)
        print("SOLVE TIME STATISTICS (solved entries only)")
        print("-" * 70)
        print(f"Total entries with timing: {time_stats['count']:,}")
        print(
            f"Total solve time:          {format_time(time_stats['total'], args.unit)}"
        )
        print(
            f"Mean solve time:           {format_time(time_stats['mean'], args.unit)}"
        )
        print(
            f"Median solve time:         {format_time(time_stats['median'], args.unit)}"
        )
        print(
            f"Std deviation:             {format_time(time_stats['std_dev'], args.unit)}"
        )
        print(f"Min solve time:            {format_time(time_stats['min'], args.unit)}")
        print(f"Max solve time:            {format_time(time_stats['max'], args.unit)}")
        print(
            f"25th percentile:           {format_time(time_stats['percentile_25'], args.unit)}"
        )
        print(
            f"75th percentile:           {format_time(time_stats['percentile_75'], args.unit)}"
        )
        print(
            f"95th percentile:           {format_time(time_stats['percentile_95'], args.unit)}"
        )

    # Detailed breakdown if requested
    if args.detailed:
        print()
        print("=" * 70)
        print("BREAKDOWN BY BENCHMARK")
        print("=" * 70)
        for benchmark in BENCHMARKS:
            entries = stats_by_benchmark[benchmark]
            if not entries:
                continue
            solved = sum(1 for e in entries if is_solved(e))
            total = len(entries)
            rate = (solved / total) * 100 if total > 0 else 0
            times = [get_execution_time(e) for e in entries if is_solved(e)]
            times = [t for t in times if t is not None]
            mean_time = statistics.mean(times) if times else None
            print(f"\n{BENCHMARK_NAMES[benchmark]}:")
            print(f"  Total: {total:,}, Solved: {solved:,}, Rate: {rate:.2f}%")
            if mean_time:
                print(f"  Mean solve time: {format_time(mean_time, args.unit)}")

        print()
        print("=" * 70)
        print("BREAKDOWN BY ENCODING")
        print("=" * 70)
        for encoding in ENCODINGS:
            entries = stats_by_encoding[encoding]
            if not entries:
                continue
            solved = sum(1 for e in entries if is_solved(e))
            total = len(entries)
            rate = (solved / total) * 100 if total > 0 else 0
            times = [get_execution_time(e) for e in entries if is_solved(e)]
            times = [t for t in times if t is not None]
            mean_time = statistics.mean(times) if times else None
            print(f"\n{ENCODING_NAMES[encoding]}:")
            print(f"  Total: {total:,}, Solved: {solved:,}, Rate: {rate:.2f}%")
            if mean_time:
                print(f"  Mean solve time: {format_time(mean_time, args.unit)}")

        print()
        print("=" * 70)
        print("DETAILED BREAKDOWN (Benchmark x Encoding)")
        print("=" * 70)
        print()
        # Table header
        header = f"{'Benchmark':<12}"
        for encoding in ENCODINGS:
            header += f" | {ENCODING_NAMES[encoding]:^15}"
        print(header)
        print("-" * len(header))

        for benchmark in BENCHMARKS:
            row = f"{BENCHMARK_NAMES[benchmark]:<12}"
            for encoding in ENCODINGS:
                entries = stats_by_both.get((benchmark, encoding), [])
                if entries:
                    solved = sum(1 for e in entries if is_solved(e))
                    total = len(entries)
                    rate = (solved / total) * 100 if total > 0 else 0
                    row += f" | {solved:>3}/{total:<3} ({rate:>5.1f}%)"
                else:
                    row += f" | {'N/A':^15}"
            print(row)

    print()
    print("=" * 70)
    return 0


if __name__ == "__main__":
    exit(main())
