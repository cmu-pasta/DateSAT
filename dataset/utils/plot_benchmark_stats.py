#!/usr/bin/env python3
"""
Script to plot benchmark statistics (#variables and #constraints) by dataset.
Generates publication-quality figures with standard deviation error bars.
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_grammar_constraints(base_path: Path) -> list[dict]:
    """Load grammar constraints from JSON file."""
    file_path = base_path / "grammar_constraints" / "benchmarks" / "constraints.json"
    with open(file_path, "r") as f:
        return json.load(f)


def load_llm_constraints(base_path: Path) -> list[dict]:
    """Load LLM constraints from JSON file."""
    file_path = base_path / "llm_constraints" / "constraints" / "constraints.json"
    with open(file_path, "r") as f:
        return json.load(f)


def load_legal_constraints(base_path: Path) -> list[dict]:
    """Load legal document constraints from JSONL file."""
    file_path = (
        base_path / "legal_doc_constraints" / "constraints" / "constraints.jsonl"
    )
    data = []
    with open(file_path, "r") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def compute_stats(data: list[dict]) -> dict:
    """Compute statistics for variables and constraints."""
    num_vars = [len(d["declarations"]) for d in data]
    num_constraints = [len(d["constraints"]) for d in data]

    return {
        "n": len(data),
        "vars_mean": np.mean(num_vars),
        "vars_std": np.std(num_vars),
        "vars_min": np.min(num_vars),
        "vars_max": np.max(num_vars),
        "constraints_mean": np.mean(num_constraints),
        "constraints_std": np.std(num_constraints),
        "constraints_min": np.min(num_constraints),
        "constraints_max": np.max(num_constraints),
    }


def plot_benchmark_stats(
    stats_dict: dict[str, dict],
    output_path: Path,
    figsize: tuple = (6, 3.5),
):
    """
    Create a grouped bar chart showing #variables and #constraints by dataset.

    Args:
        stats_dict: Dictionary mapping dataset names to their statistics.
        output_path: Path to save the figure (PDF).
        figsize: Figure size in inches (width, height).
    """
    # Use a clean style
    plt.style.use("seaborn-v0_8-whitegrid")

    # Set up publication-quality style with bold text
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
            "font.size": 10,
            "font.weight": "bold",
            "axes.labelsize": 11,
            "axes.labelweight": "bold",
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "xtick.labelsize": 10,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
            "grid.linewidth": 0.5,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    datasets = list(stats_dict.keys())
    x = np.arange(len(datasets))
    width = 0.32

    fig, ax = plt.subplots(figsize=figsize)

    # Extract data
    vars_means = [stats_dict[d]["vars_mean"] for d in datasets]
    vars_stds = [stats_dict[d]["vars_std"] for d in datasets]
    constraints_means = [stats_dict[d]["constraints_mean"] for d in datasets]
    constraints_stds = [stats_dict[d]["constraints_std"] for d in datasets]

    # Time/date inspired color palette:
    # - Midnight blue: represents time, night sky, clock faces
    # - Warm amber/gold: represents sunlight, hourglasses, calendar highlights
    colors = ["#1E3A5F", "#D4A03C"]  # Midnight blue & Amber gold
    error_colors = ["#0f1f33", "#9a7428"]  # Darker variants for error bars

    # Create bars with error bars
    bars1 = ax.bar(
        x - width / 2,
        vars_means,
        width,
        yerr=vars_stds,
        label="Variables",
        color=colors[0],
        edgecolor="white",
        linewidth=1.5,
        capsize=5,
        error_kw={"elinewidth": 1.5, "capthick": 1.5, "ecolor": error_colors[0]},
        zorder=3,
    )

    bars2 = ax.bar(
        x + width / 2,
        constraints_means,
        width,
        yerr=constraints_stds,
        label="Constraints",
        color=colors[1],
        edgecolor="white",
        linewidth=1.5,
        capsize=5,
        error_kw={"elinewidth": 1.5, "capthick": 1.5, "ecolor": error_colors[1]},
        zorder=3,
    )

    # Add value labels on top of bars
    def add_value_labels(bars, stds, color):
        for bar, std in zip(bars, stds):
            height = bar.get_height()
            ax.annotate(
                f"{height:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, height + std + 0.3),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=color,
            )

    add_value_labels(bars1, vars_stds, error_colors[0])
    add_value_labels(bars2, constraints_stds, error_colors[1])

    # Customize axes
    ax.set_ylabel("Count (mean ± std)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(datasets, fontweight="bold")

    # Add sample size annotations below x-axis labels
    for i, dataset in enumerate(datasets):
        n = stats_dict[dataset]["n"]
        ax.annotate(
            f"(n={n})",
            xy=(i, 0),
            xytext=(0, -15),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=9,
            fontweight="bold",
            color="#333333",
        )

    # Legend - positioned outside the plot area to avoid overlap
    legend = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=2,
        frameon=True,
        fancybox=True,
        shadow=False,
        framealpha=0.95,
        edgecolor="#cccccc",
        fontsize=9,
    )
    legend.get_frame().set_linewidth(0.5)
    for text in legend.get_texts():
        text.set_fontweight("bold")

    # Set y-axis to start at 0 with some headroom
    y_max = max(
        max(vars_means) + max(vars_stds), max(constraints_means) + max(constraints_stds)
    )
    ax.set_ylim(bottom=0, top=y_max * 1.2)

    # Light horizontal grid only
    ax.yaxis.grid(True, linestyle="-", alpha=0.25, zorder=0)
    ax.xaxis.grid(False)

    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18, top=0.88)

    # Save as PDF only
    pdf_path = output_path.with_suffix(".pdf")
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.05)
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def print_stats_table(stats_dict: dict[str, dict]):
    """Print statistics as a formatted table."""
    print("\n" + "=" * 70)
    print("Benchmark Statistics Summary")
    print("=" * 70)
    print(
        f"{'Dataset':<15} {'N':>6} {'Vars (mean±std)':>18} {'Constraints (mean±std)':>22}"
    )
    print("-" * 70)

    for name, stats in stats_dict.items():
        vars_str = f"{stats['vars_mean']:.1f} ± {stats['vars_std']:.1f}"
        constraints_str = (
            f"{stats['constraints_mean']:.1f} ± {stats['constraints_std']:.1f}"
        )
        print(f"{name:<15} {stats['n']:>6} {vars_str:>18} {constraints_str:>22}")

    print("-" * 70)

    # Compute overall weighted averages (weighted by number of benchmarks)
    total_n = sum(s["n"] for s in stats_dict.values())
    overall_vars_mean = (
        sum(s["vars_mean"] * s["n"] for s in stats_dict.values()) / total_n
    )
    overall_constraints_mean = (
        sum(s["constraints_mean"] * s["n"] for s in stats_dict.values()) / total_n
    )

    print(
        f"{'Overall':<15} {total_n:>6} {overall_vars_mean:>18.1f} {overall_constraints_mean:>22.1f}"
    )
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Plot benchmark statistics by dataset."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="benchmark_stats.pdf",
        help="Output file path for the figure (default: benchmark_stats.pdf)",
    )
    parser.add_argument(
        "--figsize",
        type=float,
        nargs=2,
        default=[6, 3.5],
        metavar=("WIDTH", "HEIGHT"),
        help="Figure size in inches (default: 6 3.5)",
    )
    args = parser.parse_args()

    # Determine base path (dataset directory)
    script_dir = Path(__file__).parent
    base_path = script_dir.parent

    # Load all datasets (order determines bar order: LLM, Grammar, Legal)
    print("Loading benchmark datasets...")

    stats_dict = {}

    try:
        llm_data = load_llm_constraints(base_path)
        stats_dict["LLM"] = compute_stats(llm_data)
        print(f"  LLM: {len(llm_data)} benchmarks loaded")
    except FileNotFoundError as e:
        print(f"  Warning: LLM constraints not found: {e}")

    try:
        grammar_data = load_grammar_constraints(base_path)
        stats_dict["Grammar"] = compute_stats(grammar_data)
        print(f"  Grammar: {len(grammar_data)} benchmarks loaded")
    except FileNotFoundError as e:
        print(f"  Warning: Grammar constraints not found: {e}")

    try:
        legal_data = load_legal_constraints(base_path)
        stats_dict["Legal"] = compute_stats(legal_data)
        print(f"  Legal: {len(legal_data)} benchmarks loaded")
    except FileNotFoundError as e:
        print(f"  Warning: Legal constraints not found: {e}")

    if not stats_dict:
        print("Error: No benchmark data found!")
        return 1

    # Print statistics table
    print_stats_table(stats_dict)

    # Generate plot
    output_path = Path(args.output)
    plot_benchmark_stats(
        stats_dict,
        output_path,
        figsize=tuple(args.figsize),
    )

    return 0


if __name__ == "__main__":
    exit(main())
