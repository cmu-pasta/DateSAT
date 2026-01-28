#!/usr/bin/env python3
"""
Script to generate normalized speedup plots comparing different SMT encoding techniques.
Compares execution times against a baseline (naive_int) and shows speedup/slowdown ratios.

The plot style is inspired by benchmark comparison visualizations showing
relative performance across multiple test cases.
"""

import json
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


def load_results(results_path: Path, verbose: bool = False) -> dict[str, list[dict]]:
    """
    Load all technique result files from the results directory.

    Args:
        results_path: Path to the results directory
        verbose: If True, print loading details

    Returns:
        Dictionary mapping technique name to list of constraint results
    """
    results = {}

    for technique, config in TECHNIQUES.items():
        file_path = results_path / config["file"]
        if file_path.exists():
            with open(file_path, "r") as f:
                data = json.load(f)
                results[technique] = {item["id"]: item for item in data}
                if verbose:
                    print(f"  Loaded {len(data)} from {config['file']}")
        else:
            if verbose:
                print(f"  Warning: {config['file']} not found")
            results[technique] = {}

    return results


def compute_speedups(
    results: dict[str, dict], baseline_technique: str
) -> dict[str, dict]:
    """
    Compute speedup ratios for each technique compared to the baseline.

    Speedup = baseline_time / technique_time
    - > 1 means technique is faster than baseline
    - < 1 means technique is slower than baseline
    - = 1 means same performance

    Args:
        results: Dictionary of technique results
        baseline_technique: Name of the baseline technique

    Returns:
        Dictionary mapping technique name to {constraint_id: speedup}
    """
    baseline_results = results.get(baseline_technique, {})
    if not baseline_results:
        raise ValueError(f"Baseline technique '{baseline_technique}' has no results")

    speedups = {}

    for technique, technique_results in results.items():
        speedups[technique] = {}

        for constraint_id, baseline_item in baseline_results.items():
            # Get baseline time (use TIMEOUT_SECONDS if timed out)
            baseline_time = baseline_item.get("execution_time")
            if baseline_item.get("status") == "timeout":
                baseline_time = TIMEOUT_SECONDS
            if baseline_time is None or baseline_time <= 0:
                continue

            # Skip if technique doesn't have this constraint
            if constraint_id not in technique_results:
                continue

            technique_item = technique_results[constraint_id]

            # Get technique time (use TIMEOUT_SECONDS if timed out)
            technique_time = technique_item.get("execution_time")
            if technique_item.get("status") == "timeout":
                technique_time = TIMEOUT_SECONDS
            if technique_time is None or technique_time <= 0:
                continue

            # Compute speedup
            speedup = baseline_time / technique_time
            speedups[technique][constraint_id] = speedup

    return speedups


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
):
    """
    Create a normalized speedup plot comparing all techniques.

    Args:
        speedups: Dictionary mapping technique name to {constraint_id: speedup}
        sorted_constraint_ids: List of constraint IDs in sorted order
        output_path: Path to save the output figure
        title: Plot title
    """
    # Set up the figure with publication-quality settings
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "axes.linewidth": 0.6,
            "axes.edgecolor": "#333333",
            "axes.facecolor": "#fafafa",
            "figure.facecolor": "white",
        }
    )

    n_constraints = len(sorted_constraint_ids)

    # Adjust figure size and marker size based on number of constraints
    if n_constraints > 300:
        fig_width = 12
        marker_size = 20
        marker_alpha = 0.7
        line_width = 1.0
    elif n_constraints > 150:
        fig_width = 11
        marker_size = 30
        marker_alpha = 0.75
        line_width = 1.2
    else:
        fig_width = 10
        marker_size = 40
        marker_alpha = 0.8
        line_width = 1.4

    fig, ax = plt.subplots(figsize=(fig_width, 4))

    # Add background shading for speedup/slowdown regions
    ax.axhspan(1, 100000, facecolor="#e8f5e9", alpha=0.4, zorder=0)  # Green for speedup
    ax.axhspan(0.00001, 1, facecolor="#ffebee", alpha=0.4, zorder=0)  # Red for slowdown

    # Add horizontal reference line at y=1 (baseline performance)
    ax.axhline(y=1, color="#333333", linestyle="-", linewidth=1.5, alpha=0.9, zorder=2)

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
        y_min = max(0.001, min(all_speedups) * 0.5)
        y_max = min(100000, max(all_speedups) * 2)
    else:
        y_min, y_max = 0.01, 1000

    ax.set_ylim(y_min, y_max)

    # X-axis settings - tighter margins
    ax.set_xlim(-1, n_constraints)

    # Remove x-tick labels (too many constraints)
    ax.set_xticks([])

    # Labels
    ax.set_xlabel(
        f"Constraint (n={n_constraints}, sorted by baseline time)",
        fontweight="medium",
        fontsize=9,
    )
    ax.set_ylabel("Speedup", fontweight="medium", fontsize=9)

    # Grid - only horizontal, subtle
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, zorder=1, color="#bbbbbb")
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
        borderpad=0.5,
        handletextpad=0.4,
        columnspacing=0.8,
        fontsize=8,
    )
    legend.get_frame().set_linewidth(0.4)

    # Title
    ax.set_title(title, fontweight="bold", pad=10, fontsize=10)

    # Add annotations for speedup/slowdown regions (smaller font)
    ax.text(
        0.99,
        0.97,
        "Faster",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="#2e7d32",
        fontstyle="italic",
        alpha=0.7,
    )
    ax.text(
        0.99,
        0.03,
        "Slower",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="#c62828",
        fontstyle="italic",
        alpha=0.7,
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


def process_dataset(dataset_name: str, dataset_config: dict):
    """
    Process a single dataset and generate its speedup plot.

    Args:
        dataset_name: Name of the dataset
        dataset_config: Configuration dict with path, title, output_name
    """
    results_path = dataset_config["path"]
    title = dataset_config["title"]
    output_name = dataset_config["output_name"]

    if not results_path.exists():
        print(f"  [!] {dataset_name}: Results not found")
        return False

    # Load all results
    results = load_results(results_path, verbose=False)

    # Check we have baseline
    if BASELINE_TECHNIQUE not in results or not results[BASELINE_TECHNIQUE]:
        print(f"  [!] {dataset_name}: Baseline not found")
        return False

    # Get sorted constraint IDs (timeouts treated as 60s)
    sorted_constraint_ids = get_sorted_constraint_ids(results, BASELINE_TECHNIQUE)

    print(f"\n[{dataset_name.upper()}] {len(sorted_constraint_ids)} constraints")

    # Compute speedups
    speedups = compute_speedups(results, BASELINE_TECHNIQUE)

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
    )

    print(f"  -> {output_path.with_suffix('.pdf').name}")

    return True


def process_combined_datasets():
    """
    Process all datasets combined into a single plot.
    """
    # Collect all results from all datasets with unique IDs
    combined_results = {technique: {} for technique in TECHNIQUES}
    dataset_counts = []

    for dataset_name, dataset_config in DATASETS.items():
        results_path = dataset_config["path"]

        if not results_path.exists():
            continue

        count = 0
        for technique, config in TECHNIQUES.items():
            file_path = results_path / config["file"]
            if file_path.exists():
                with open(file_path, "r") as f:
                    data = json.load(f)
                    # Add dataset prefix to make IDs unique
                    for item in data:
                        unique_id = f"{dataset_name}_{item['id']}"
                        combined_results[technique][unique_id] = item
                    if technique == BASELINE_TECHNIQUE:
                        count = len(data)

        dataset_counts.append(f"{dataset_name}={count}")

    # Check we have baseline
    if not combined_results[BASELINE_TECHNIQUE]:
        print("  [!] COMBINED: No baseline results found")
        return False

    # Get sorted constraint IDs
    sorted_constraint_ids = get_sorted_constraint_ids(
        combined_results, BASELINE_TECHNIQUE
    )

    print(
        f"\n[COMBINED] {len(sorted_constraint_ids)} constraints ({', '.join(dataset_counts)})"
    )

    # Compute speedups
    speedups = compute_speedups(combined_results, BASELINE_TECHNIQUE)

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
    )

    print(f"  -> {output_path.with_suffix('.pdf').name}")

    return True


def main():
    """Main entry point."""
    print("\nNormalized Speedup Plot Generator")
    print(
        f"Baseline: {TECHNIQUES[BASELINE_TECHNIQUE]['label']} | Timeouts: {TIMEOUT_SECONDS}s"
    )

    success_count = 0
    for dataset_name, dataset_config in DATASETS.items():
        if process_dataset(dataset_name, dataset_config):
            success_count += 1

    # Also generate combined plot
    if process_combined_datasets():
        success_count += 1

    print(f"\nDone! Generated {success_count} plots.")


if __name__ == "__main__":
    main()
