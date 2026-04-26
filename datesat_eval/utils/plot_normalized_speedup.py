#!/usr/bin/env python3
"""
Script to generate normalized speedup plots comparing different SMT encoding techniques.
Compares execution times against a baseline (naive_int) and shows speedup/slowdown ratios.

The plot style is inspired by benchmark comparison visualizations showing
relative performance across multiple test cases.
"""

import json
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Hardcoded paths to constraint results
DATASETS = {
    "legal_doc": {
        "path": Path(__file__).parent.parent / "legal_doc_constraints" / "results",
        "title": "Normalized Speedup Comparison on Legally Grounded Constraints",
        "output_name": "normalized_speedup_legal_doc",
    },
    "grammar": {
        "path": Path(__file__).parent.parent / "grammar_constraints" / "results",
        "title": "Normalized Speedup Comparison on Grammar-Sampled Constraints",
        "output_name": "normalized_speedup_grammar",
    },
    "llm": {
        "path": Path(__file__).parent.parent / "llm_constraints" / "results",
        "title": "Normalized Speedup Comparison on LLM-Synthesized Constraints",
        "output_name": "normalized_speedup_llm",
    },
}

# Technique files and display names with a refined color palette
TECHNIQUES = {
    "naive_int": {
        "file": "naive_int.json",
        "label": "Naive (baseline)",
        "marker": "x",
        "color": "#E91E63",
    },
    "epoch_days_int": {
        "file": "epoch_days_int.json",
        "label": "Epoch Days",
        "marker": "o",
        "color": "#FF9800",
    },
    "hybrid_int": {
        "file": "hybrid_int.json",
        "label": "Hybrid",
        "marker": "^",
        "color": "#4CAF50",
    },
    "alpha_beta_int": {
        "file": "alpha_beta_int.json",
        "label": "Alpha-Beta",
        "marker": "+",
        "color": "#2196F3",
    },
    "alpha_beta_table_int": {
        "file": "alpha_beta_table_int.json",
        "label": "Alpha-Beta Table",
        "marker": "D",
        "color": "#9C27B0",
    },
}

BASELINE_TECHNIQUE = "naive_int"

# Timeout value in seconds (use this for constraints that timed out)
TIMEOUT_SECONDS = 60.0

# Speedup value when baseline finishes but technique times out
TIMEOUT_SPEEDUP = 1e-3  # 0.001


def get_run_dirs(results_dir: Path) -> list[Path]:
    """Return run_* subdirectories sorted numerically."""
    runs = [d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    return sorted(runs, key=lambda d: int(d.name.split("_")[1]))


def load_results(results_path: Path, verbose: bool = False) -> dict[str, dict[str, dict]]:
    """
    Load all technique result files across run_* subdirectories and aggregate.

    For each constraint, execution_time is averaged across runs.  Status is set
    to "timeout" only when every run timed out; otherwise the most common
    non-timeout status is kept.

    Args:
        results_path: Path to the results directory containing run_* subdirs
        verbose: If True, print loading details

    Returns:
        Dictionary mapping technique name to {constraint_id: aggregated_item}
    """
    run_dirs = get_run_dirs(results_path)
    if not run_dirs:
        if verbose:
            print(f"  Warning: No run_* directories found in {results_path}")
        return {technique: {} for technique in TECHNIQUES}

    results = {}

    for technique, config in TECHNIQUES.items():
        times_by_id: dict[str, list[float]] = {}
        statuses_by_id: dict[str, list[str]] = {}
        base_items: dict[str, dict] = {}

        for run_dir in run_dirs:
            file_path = run_dir / config["file"]
            if not file_path.exists():
                continue
            with open(file_path, "r") as f:
                data = json.load(f)
            for item in data:
                pid = item["id"]
                if pid not in base_items:
                    base_items[pid] = dict(item)
                statuses_by_id.setdefault(pid, []).append(item.get("status", "unknown"))
                if item.get("execution_time") is not None:
                    times_by_id.setdefault(pid, []).append(item["execution_time"])

        aggregated: dict[str, dict] = {}
        for pid, base_item in base_items.items():
            entry = dict(base_item)
            if pid in times_by_id:
                entry["execution_time"] = statistics.mean(times_by_id[pid])

            statuses = statuses_by_id.get(pid, [])
            if all(s == "timeout" for s in statuses):
                entry["status"] = "timeout"
            else:
                non_timeout = [s for s in statuses if s != "timeout"]
                entry["status"] = max(set(non_timeout), key=non_timeout.count) if non_timeout else "timeout"

            aggregated[pid] = entry

        results[technique] = aggregated
        if verbose:
            print(f"  Loaded {len(aggregated)} from {config['file']} across {len(run_dirs)} runs")

    return results


def compute_speedups(
    results: dict[str, dict], baseline_technique: str
) -> tuple[dict[str, dict], int]:
    """
    Compute speedup ratios for each technique compared to the baseline.

    Speedup = baseline_time / technique_time
    - > 1 means technique is faster than baseline
    - < 1 means technique is slower than baseline
    - = 1 means same performance

    Special cases:
    - If baseline times out: use TIMEOUT_SECONDS (60s) for baseline time
    - If baseline finishes but technique times out: speedup = TIMEOUT_SPEEDUP (10^-4)
    - If both timeout: skip the datapoint

    Args:
        results: Dictionary of technique results
        baseline_technique: Name of the baseline technique

    Returns:
        Tuple of (speedups dict, count of both-timeout dropped constraints)
    """
    baseline_results = results.get(baseline_technique, {})
    if not baseline_results:
        raise ValueError(f"Baseline technique '{baseline_technique}' has no results")

    speedups = {}
    both_timeout_ids = set()  # Track constraints where all techniques both-timeout

    for technique, technique_results in results.items():
        speedups[technique] = {}

        for constraint_id, baseline_item in baseline_results.items():
            baseline_timed_out = baseline_item.get("status") == "timeout"
            baseline_time = baseline_item.get("execution_time")

            # Skip if baseline has no valid execution time
            if baseline_time is None or baseline_time <= 0:
                continue

            # Skip if technique doesn't have this constraint
            if constraint_id not in technique_results:
                continue

            technique_item = technique_results[constraint_id]
            technique_timed_out = technique_item.get("status") == "timeout"
            technique_time = technique_item.get("execution_time")

            # Skip if technique has no valid execution time
            if technique_time is None or technique_time <= 0:
                continue

            # Handle timeout cases
            if baseline_timed_out and technique_timed_out:
                # Both timed out: skip this datapoint
                both_timeout_ids.add(constraint_id)
                continue
            elif baseline_timed_out:
                # Baseline timed out, technique finished: use TIMEOUT_SECONDS for baseline
                speedup = TIMEOUT_SECONDS / technique_time
            elif technique_timed_out:
                # Baseline finished, technique timed out: use TIMEOUT_SPEEDUP
                speedup = TIMEOUT_SPEEDUP
            else:
                # Neither timed out: normal computation
                speedup = baseline_time / technique_time

            speedups[technique][constraint_id] = speedup

    # Count constraints that were dropped for ALL techniques (both-timeout for all)
    # A constraint is truly dropped only if no technique has a valid speedup for it
    all_valid_ids = set()
    for technique in speedups:
        if technique != baseline_technique:
            all_valid_ids.update(speedups[technique].keys())

    dropped_count = len(baseline_results) - len(all_valid_ids)

    return speedups, dropped_count


def get_sorted_constraint_ids(
    results: dict[str, dict], baseline_technique: str
) -> list[str]:
    """
    Get constraint IDs sorted by baseline execution time (ascending).
    Timeouts are treated as TIMEOUT_SECONDS.

    Args:
        results: Dictionary of technique results
        baseline_technique: Name of the baseline technique

    Returns:
        List of constraint IDs sorted by baseline time
    """
    baseline_results = results.get(baseline_technique, {})

    # Get all constraints with valid times (treat timeouts as TIMEOUT_SECONDS)
    valid_constraints = []
    for constraint_id, item in baseline_results.items():
        exec_time = item.get("execution_time")
        if item.get("status") == "timeout":
            exec_time = TIMEOUT_SECONDS
        if exec_time is not None and exec_time > 0:
            valid_constraints.append((constraint_id, exec_time))

    # Sort by execution time
    valid_constraints.sort(key=lambda x: x[1])

    return [constraint_id for constraint_id, _ in valid_constraints]


def plot_normalized_speedup(
    speedups: dict[str, dict],
    sorted_constraint_ids: list[str],
    output_path: Path,
    title: str = "Normalized Speedup vs Naive (Baseline)",
    baseline_time_range: tuple[float, float] = None,
):
    """
    Create a normalized speedup plot comparing all techniques.

    Args:
        speedups: Dictionary mapping technique name to {constraint_id: speedup}
        sorted_constraint_ids: List of constraint IDs in sorted order
        output_path: Path to save the output figure
        title: Plot title
        baseline_time_range: Tuple of (min_time, max_time) in seconds for baseline
    """
    # Set up the figure with publication-quality settings (larger for paper)
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 14,
            "axes.labelsize": 16,
            "axes.titlesize": 18,
            "legend.fontsize": 13,
            "xtick.labelsize": 13,
            "ytick.labelsize": 13,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "axes.linewidth": 1.2,
            "axes.edgecolor": "#333333",
            "axes.facecolor": "#fafafa",
            "figure.facecolor": "white",
        }
    )

    n_constraints = len(sorted_constraint_ids)

    # Adjust figure size and marker size based on number of constraints
    if n_constraints > 300:
        fig_width = 16
        fig_height = 8
        marker_size = 35
        marker_alpha = 0.75
        line_width = 1.8
    elif n_constraints > 150:
        fig_width = 15
        fig_height = 8
        marker_size = 45
        marker_alpha = 0.8
        line_width = 2.0
    else:
        fig_width = 14
        fig_height = 7.5
        marker_size = 55
        marker_alpha = 0.85
        line_width = 2.2

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # Add background shading for speedup/slowdown regions
    ax.axhspan(1, 100000, facecolor="#e8f5e9", alpha=0.4, zorder=0)  # Green for speedup
    ax.axhspan(0.00001, 1, facecolor="#ffebee", alpha=0.4, zorder=0)  # Red for slowdown

    # Add horizontal reference line at y=1 (baseline performance)
    ax.axhline(y=1, color="#333333", linestyle="-", linewidth=2.5, alpha=0.9, zorder=2)

    # Plot each technique (except baseline which will be shown as reference line)
    for technique, config in TECHNIQUES.items():
        if technique == BASELINE_TECHNIQUE:
            continue  # Skip baseline, it will be a reference line at y=1

        technique_speedups = speedups.get(technique, {})

        # Get speedup values for sorted constraints
        y_values = []
        x_plot = []

        for i, constraint_id in enumerate(sorted_constraint_ids):
            if constraint_id in technique_speedups:
                y_values.append(technique_speedups[constraint_id])
                x_plot.append(i)

        if y_values:
            scatter_kwargs = {
                "marker": config["marker"],
                "c": config["color"],
                "s": marker_size,
                "label": config["label"],
                "alpha": marker_alpha,
                "zorder": 4,
            }
            # For unfilled markers (+, x), use linewidths; for filled markers, use edgecolors
            if config["marker"] in ["+", "x"]:
                scatter_kwargs["linewidths"] = line_width
            else:
                scatter_kwargs["linewidths"] = 0.5
                scatter_kwargs["edgecolors"] = "white"

            ax.scatter(x_plot, y_values, **scatter_kwargs)

    # Set logarithmic scale for y-axis
    ax.set_yscale("log")

    # Dynamic y-axis limits based on data
    all_speedups = []
    for technique, technique_speedups in speedups.items():
        if technique != BASELINE_TECHNIQUE:
            all_speedups.extend(
                [v for v in technique_speedups.values() if v is not None and v > 0]
            )

    if all_speedups:
        y_min = max(
            0.0005, min(all_speedups) * 0.5
        )  # Extended below TIMEOUT_SPEEDUP (0.001)
        y_max = min(100000, max(all_speedups) * 2)
    else:
        y_min, y_max = 0.01, 1000

    ax.set_ylim(y_min, y_max)

    # X-axis settings - tighter margins
    ax.set_xlim(-1, n_constraints)

    # Remove x-tick labels (too many constraints)
    ax.set_xticks([])

    # Labels
    if baseline_time_range:
        min_t, max_t = baseline_time_range
        xlabel = f"Constraint (n={n_constraints}, sorted by baseline time: {min_t:.3f}s – {max_t:.1f}s)"
    else:
        xlabel = f"Constraint (n={n_constraints}, sorted by baseline time)"
    ax.set_xlabel(xlabel, fontweight="medium", fontsize=25, labelpad=12)
    ax.set_ylabel("Speedup (log scale)", fontweight="medium", fontsize=25)

    # Grid - only horizontal, subtle
    ax.yaxis.grid(
        True, linestyle="--", alpha=0.3, zorder=1, color="#bbbbbb", linewidth=0.8
    )
    ax.xaxis.grid(False)

    # Remove top and right spines for cleaner look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend - inside the plot area, top left
    legend = ax.legend(
        loc="upper left",
        frameon=True,
        fancybox=False,
        shadow=False,
        framealpha=0.9,
        edgecolor="#dddddd",
        borderpad=0.8,
        handletextpad=0.6,
        columnspacing=1.2,
        fontsize=18,
        markerscale=1.3,
    )
    legend.get_frame().set_linewidth(1.0)

    # Title
    ax.set_title(title, fontweight="bold", pad=18, fontsize=26)

    # Add annotations for speedup/slowdown regions
    ax.text(
        0.99,
        0.97,
        "Faster",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=18,
        color="#2e7d32",
        fontweight="bold",
        alpha=0.7,
    )
    ax.text(
        0.99,
        0.03,
        "Slower",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=18,
        color="#c62828",
        fontweight="bold",
        alpha=0.8,
    )

    # Adjust layout
    plt.tight_layout()

    # Save as PDF only
    pdf_path = output_path.with_suffix(".pdf")
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.1)
    plt.close()


def print_statistics(speedups: dict[str, dict], sorted_constraint_ids: list[str]):
    """
    Print summary statistics for each technique.

    Args:
        speedups: Dictionary mapping technique name to {constraint_id: speedup}
        sorted_constraint_ids: List of constraint IDs
    """
    print(f"\n  {'Technique':<20} {'Median':>10} {'Mean':>10}")
    print(f"  {'-' * 42}")

    for technique, config in TECHNIQUES.items():
        if technique == BASELINE_TECHNIQUE:
            continue

        technique_speedups = speedups.get(technique, {})
        values = [
            technique_speedups.get(cid)
            for cid in sorted_constraint_ids
            if cid in technique_speedups
        ]
        values = [v for v in values if v is not None]

        if values:
            median = np.median(values)
            mean = np.mean(values)
            print(f"  {config['label']:<20} {median:>9.2f}x {mean:>9.2f}x")
        else:
            print(f"  {config['label']:<20} {'N/A':>10}")


def process_datesatbench(datesatbench_name: str, datesatbench_config: dict):
    """
    Process a single datesatbench and generate its speedup plot.

    Args:
        datesatbench_name: Name of the datesatbench
        datesatbench_config: Configuration dict with path, title, output_name
    """
    results_path = datesatbench_config["path"]
    title = datesatbench_config["title"]
    output_name = datesatbench_config["output_name"]

    if not results_path.exists():
        print(f"  [!] {datesatbench_name}: Results not found")
        return False

    # Load all results
    results = load_results(results_path, verbose=False)

    # Check we have baseline
    if BASELINE_TECHNIQUE not in results or not results[BASELINE_TECHNIQUE]:
        print(f"  [!] {datesatbench_name}: Baseline not found")
        return False

    # Get sorted constraint IDs (timeouts treated as 60s)
    sorted_constraint_ids = get_sorted_constraint_ids(results, BASELINE_TECHNIQUE)
    total_constraints = len(sorted_constraint_ids)

    # Compute speedups
    speedups, dropped_count = compute_speedups(results, BASELINE_TECHNIQUE)

    # Get actual count of constraints with valid speedups
    valid_constraint_ids = set()
    for technique in speedups:
        if technique != BASELINE_TECHNIQUE:
            valid_constraint_ids.update(speedups[technique].keys())
    actual_count = len(valid_constraint_ids)

    if dropped_count > 0:
        print(
            f"\n[{datesatbench_name.upper()}] {actual_count} constraints ({dropped_count} dropped, both timed out)"
        )
    else:
        print(f"\n[{datesatbench_name.upper()}] {actual_count} constraints")

    # Filter sorted_constraint_ids to only include valid ones
    sorted_constraint_ids = [
        cid for cid in sorted_constraint_ids if cid in valid_constraint_ids
    ]

    # Compute baseline time range
    baseline_results = results[BASELINE_TECHNIQUE]
    baseline_times = []
    for cid in sorted_constraint_ids:
        if cid in baseline_results:
            t = baseline_results[cid].get("execution_time")
            if baseline_results[cid].get("status") == "timeout":
                t = TIMEOUT_SECONDS
            if t and t > 0:
                baseline_times.append(t)
    baseline_time_range = (
        (min(baseline_times), max(baseline_times)) if baseline_times else None
    )

    # Print statistics
    print_statistics(speedups, sorted_constraint_ids)

    # Generate plot
    output_path = Path(__file__).parent / "results" / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_normalized_speedup(
        speedups,
        sorted_constraint_ids,
        output_path,
        title=title,
        baseline_time_range=baseline_time_range,
    )

    print(f"  -> {output_path.with_suffix('.pdf').name}")

    return True


def process_combined_datesatbenchs():
    """
    Process all datesatbenchs combined into a single plot.
    """
    # Collect all results from all datesatbenchs with unique IDs
    combined_results = {technique: {} for technique in TECHNIQUES}
    datesatbench_counts = []

    for datesatbench_name, datesatbench_config in DATASETS.items():
        results_path = datesatbench_config["path"]

        if not results_path.exists():
            continue

        ds_results = load_results(results_path, verbose=False)
        count = 0
        for technique in TECHNIQUES:
            for pid, item in ds_results[technique].items():
                unique_id = f"{datesatbench_name}_{pid}"
                combined_results[technique][unique_id] = item
            if technique == BASELINE_TECHNIQUE:
                count = len(ds_results[technique])

        datesatbench_counts.append(f"{datesatbench_name}={count}")

    # Check we have baseline
    if not combined_results[BASELINE_TECHNIQUE]:
        print("  [!] COMBINED: No baseline results found")
        return False

    # Get sorted constraint IDs
    sorted_constraint_ids = get_sorted_constraint_ids(
        combined_results, BASELINE_TECHNIQUE
    )
    total_constraints = len(sorted_constraint_ids)

    # Compute speedups
    speedups, dropped_count = compute_speedups(combined_results, BASELINE_TECHNIQUE)

    # Get actual count of constraints with valid speedups
    valid_constraint_ids = set()
    for technique in speedups:
        if technique != BASELINE_TECHNIQUE:
            valid_constraint_ids.update(speedups[technique].keys())
    actual_count = len(valid_constraint_ids)

    if dropped_count > 0:
        print(
            f"\n[COMBINED] {actual_count} constraints ({dropped_count} dropped) from {', '.join(datesatbench_counts)}"
        )
    else:
        print(
            f"\n[COMBINED] {actual_count} constraints from {', '.join(datesatbench_counts)}"
        )

    # Filter sorted_constraint_ids to only include valid ones
    sorted_constraint_ids = [
        cid for cid in sorted_constraint_ids if cid in valid_constraint_ids
    ]

    # Compute baseline time range
    baseline_results = combined_results[BASELINE_TECHNIQUE]
    baseline_times = []
    for cid in sorted_constraint_ids:
        if cid in baseline_results:
            t = baseline_results[cid].get("execution_time")
            if baseline_results[cid].get("status") == "timeout":
                t = TIMEOUT_SECONDS
            if t and t > 0:
                baseline_times.append(t)
    baseline_time_range = (
        (min(baseline_times), max(baseline_times)) if baseline_times else None
    )

    # Print statistics
    print_statistics(speedups, sorted_constraint_ids)

    # Generate plot
    output_path = Path(__file__).parent / "results" / "normalized_speedup_combined"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_normalized_speedup(
        speedups,
        sorted_constraint_ids,
        output_path,
        title="Normalized Speedup Comparison (All Constraints Combined)",
        baseline_time_range=baseline_time_range,
    )

    print(f"  -> {output_path.with_suffix('.pdf').name}")

    return True


def main():
    """Main entry point."""
    print("\nNormalized Speedup Plot Generator")
    print(f"Baseline: {TECHNIQUES[BASELINE_TECHNIQUE]['label']}")
    print(f"  - Baseline timeout: use {TIMEOUT_SECONDS}s")
    print(f"  - Technique timeout (baseline ok): speedup = {TIMEOUT_SPEEDUP}")
    print(f"  - Both timeout: dropped")

    success_count = 0
    for datesatbench_name, datesatbench_config in DATASETS.items():
        if process_datesatbench(datesatbench_name, datesatbench_config):
            success_count += 1

    # Also generate combined plot
    if process_combined_datesatbenchs():
        success_count += 1

    print(f"\nDone! Generated {success_count} plots.")


if __name__ == "__main__":
    main()
