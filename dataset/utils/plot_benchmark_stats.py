#!/usr/bin/env python3
"""
Script to plot benchmark statistics (#variables and #constraints) by dataset.
Generates publication-quality figures with standard deviation error bars.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add the project root to sys.path to import datesmt module
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lark import Token, Tree

from datesmt.constraint_parser import ConstraintParser


def extract_atoms_from_constraint(
    constraint_str: str, parser: ConstraintParser
) -> list[str]:
    """
    Extract all atomic comparisons from a constraint string.

    Atoms are the basic comparison expressions (date_comparison or int_comparison)
    that cannot be broken down further into boolean sub-expressions.

    For example, given:
        A==Date(2000,1,1) && (B>C)->(C>A || C==D)

    This function returns:
        ['A == Date(2000, 1, 1)', 'B > C', 'C > A', 'C == D']

    Args:
        constraint_str: The constraint string to parse
        parser: A ConstraintParser instance

    Returns:
        List of atom strings found in the constraint
    """
    atoms = []

    try:
        # Parse the constraint to get the parse tree
        tree = parser.parser.parse(constraint_str)

        # Walk the tree to find all comparison nodes
        _extract_atoms_from_tree(tree, atoms)

    except Exception as e:
        # If parsing fails, return empty list with a warning
        print(
            f"  Warning: Could not parse constraint for atom extraction: {constraint_str[:50]}... ({e})"
        )
        return []

    return atoms


def _extract_atoms_from_tree(tree, atoms: list[str]) -> None:
    """
    Recursively walk the parse tree and extract all comparison atoms.

    Args:
        tree: Lark parse tree node
        atoms: List to append atom strings to
    """
    if isinstance(tree, Token):
        return

    if not isinstance(tree, Tree):
        return

    rule = tree.data

    # date_comparison and int_comparison are the atomic comparisons
    if rule in ["date_comparison", "int_comparison"]:
        # Reconstruct the atom string from the tree
        atom_str = _tree_to_string(tree)
        atoms.append(atom_str)
        # Don't recurse into children - we've captured this atom
        return

    # Recurse into children for other nodes
    for child in tree.children:
        if isinstance(child, Tree):
            _extract_atoms_from_tree(child, atoms)


def _tree_to_string(tree) -> str:
    """
    Convert a parse tree node back to a string representation.

    Args:
        tree: Lark parse tree node

    Returns:
        String representation of the tree
    """
    if isinstance(tree, Token):
        return str(tree)

    if not isinstance(tree, Tree):
        return str(tree)

    rule = tree.data

    # Handle specific node types
    if rule == "date_comparison" or rule == "int_comparison":
        # comparison: expr op expr
        if len(tree.children) >= 3:
            left = _tree_to_string(tree.children[0])
            op = _tree_to_string(tree.children[1])
            right = _tree_to_string(tree.children[2])
            return f"{left} {op} {right}"

    if rule == "comparison_op":
        # The operator is in the children
        if tree.children:
            return str(tree.children[0])
        return ""

    if rule == "date_constructor":
        # Date(year, month, day)
        args = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) not in ["(", ")", ","]
        ]
        return f"Date({', '.join(args)})"

    if rule == "period_constructor":
        # Period(years, months, days)
        args = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) not in ["(", ")", ","]
        ]
        return f"Period({', '.join(args)})"

    if rule == "variable":
        return str(tree.children[0])

    if rule == "int_const":
        return str(tree.children[0])

    if rule == "date_field_access":
        # e.g., x.year
        date_expr = _tree_to_string(tree.children[0])
        field = (
            _tree_to_string(tree.children[2])
            if len(tree.children) > 2
            else _tree_to_string(tree.children[1])
        )
        return f"{date_expr}.{field}"

    if rule == "date_field":
        return str(tree.children[0])

    if rule in ["date_add_period", "int_add", "period_add"]:
        parts = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) != "+"
        ]
        return " + ".join(parts)

    if rule in ["date_sub_period", "int_sub", "period_sub"]:
        parts = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) != "-"
        ]
        return " - ".join(parts)

    if rule in ["int_mul", "int_mul_period", "period_mul_int"]:
        parts = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) != "*"
        ]
        return " * ".join(parts)

    if rule == "int_neg":
        parts = [
            _tree_to_string(child)
            for child in tree.children
            if not isinstance(child, Token) or str(child) != "-"
        ]
        if parts:
            return f"-{parts[0]}"
        return "-"

    # Default: join all children
    parts = [_tree_to_string(child) for child in tree.children]
    return " ".join(parts)


def count_atoms_in_benchmark(
    benchmark: dict, parser: ConstraintParser
) -> tuple[int, list[str]]:
    """
    Count the total number of atoms in a benchmark's constraints.

    Args:
        benchmark: A benchmark dictionary with 'constraints' list
        parser: A ConstraintParser instance

    Returns:
        Tuple of (total atom count, list of all atoms)
    """
    all_atoms = []

    for constraint_str in benchmark.get("constraints", []):
        atoms = extract_atoms_from_constraint(constraint_str, parser)
        all_atoms.extend(atoms)

    return len(all_atoms), all_atoms


def write_atoms_log(
    data_dict: dict[str, list[dict]], output_path: Path, parser: ConstraintParser
):
    """
    Write a log file containing all atoms extracted from each benchmark.

    Args:
        data_dict: Dictionary mapping dataset names to their benchmark data
        output_path: Path to the output log file
        parser: A ConstraintParser instance
    """
    with open(output_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("ATOMS LOG - Extracted atomic comparisons from all benchmarks\n")
        f.write("=" * 80 + "\n\n")

        total_atoms = 0
        total_benchmarks = 0

        for dataset_name, data in data_dict.items():
            f.write(f"\n{'='*80}\n")
            f.write(f"DATASET: {dataset_name}\n")
            f.write(f"{'='*80}\n\n")

            dataset_atoms = 0

            for benchmark in data:
                benchmark_id = benchmark.get("id", "unknown")
                constraints = benchmark.get("constraints", [])

                f.write(f"\n--- Benchmark: {benchmark_id} ---\n")
                f.write(f"Number of constraint strings: {len(constraints)}\n")

                benchmark_atoms = []
                for i, constraint_str in enumerate(constraints, 1):
                    atoms = extract_atoms_from_constraint(constraint_str, parser)
                    benchmark_atoms.extend(atoms)

                    f.write(f"\n  Constraint {i}: {constraint_str}\n")
                    f.write(f"  Atoms found ({len(atoms)}):\n")
                    for j, atom in enumerate(atoms, 1):
                        f.write(f"    {j}. {atom}\n")

                f.write(f"\n  Total atoms in benchmark: {len(benchmark_atoms)}\n")
                dataset_atoms += len(benchmark_atoms)
                total_benchmarks += 1

            f.write(f"\n{'='*80}\n")
            f.write(f"DATASET SUMMARY: {dataset_name}\n")
            f.write(f"  Total benchmarks: {len(data)}\n")
            f.write(f"  Total atoms: {dataset_atoms}\n")
            f.write(f"{'='*80}\n")

            total_atoms += dataset_atoms

        f.write(f"\n\n{'='*80}\n")
        f.write(f"OVERALL SUMMARY\n")
        f.write(f"  Total benchmarks: {total_benchmarks}\n")
        f.write(f"  Total atoms: {total_atoms}\n")
        f.write(f"{'='*80}\n")

    print(f"Atoms log written to: {output_path}")


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


def compute_stats(data: list[dict], parser: ConstraintParser = None) -> dict:
    """
    Compute statistics for variables and atoms.

    Args:
        data: List of benchmark dictionaries
        parser: Optional ConstraintParser instance for atom extraction.
                If None, falls back to counting constraint strings.

    Returns:
        Dictionary with statistics for variables and atoms/constraints.
    """
    num_vars = [len(d["declarations"]) for d in data]

    # Count atoms if parser is provided, otherwise count constraint strings
    if parser is not None:
        num_atoms = []
        for d in data:
            atom_count, _ = count_atoms_in_benchmark(d, parser)
            num_atoms.append(atom_count)
    else:
        # Fallback: count constraint strings (legacy behavior)
        num_atoms = [len(d["constraints"]) for d in data]

    return {
        "n": len(data),
        "vars_mean": np.mean(num_vars),
        "vars_std": np.std(num_vars),
        "vars_min": np.min(num_vars),
        "vars_max": np.max(num_vars),
        "atoms_mean": np.mean(num_atoms),
        "atoms_std": np.std(num_atoms),
        "atoms_min": np.min(num_atoms),
        "atoms_max": np.max(num_atoms),
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
    atoms_means = [stats_dict[d]["atoms_mean"] for d in datasets]
    atoms_stds = [stats_dict[d]["atoms_std"] for d in datasets]

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
        atoms_means,
        width,
        yerr=atoms_stds,
        label="Atoms",
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
                f"{height:.1f} ± {std:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, height + std + 0.3),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=color,
            )

    add_value_labels(bars1, vars_stds, error_colors[0])
    add_value_labels(bars2, atoms_stds, error_colors[1])

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
            xytext=(0, -25),
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
    y_max = max(max(vars_means) + max(vars_stds), max(atoms_means) + max(atoms_stds))
    ax.set_ylim(bottom=0, top=y_max * 1.2)

    # Light horizontal grid only
    ax.yaxis.grid(True, linestyle="-", alpha=0.25, zorder=0)
    ax.xaxis.grid(False)

    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.20, top=0.88)

    # Save as PDF only
    pdf_path = output_path.with_suffix(".pdf")
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.05)
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def print_stats_table(stats_dict: dict[str, dict]):
    """Print statistics as a formatted table."""
    print("\n" + "=" * 90)
    print("Benchmark Statistics Summary")
    print("=" * 90)
    print(f"{'Dataset':<35} {'N':>6} {'Vars (mean±std)':>18} {'Atoms (mean±std)':>22}")
    print("-" * 90)

    for name, stats in stats_dict.items():
        # Replace newlines with spaces for table display
        display_name = name.replace("\n", " ")
        vars_str = f"{stats['vars_mean']:.1f} ± {stats['vars_std']:.1f}"
        atoms_str = f"{stats['atoms_mean']:.1f} ± {stats['atoms_std']:.1f}"
        print(f"{display_name:<35} {stats['n']:>6} {vars_str:>18} {atoms_str:>22}")

    print("-" * 90)

    # Compute overall weighted averages (weighted by number of benchmarks)
    total_n = sum(s["n"] for s in stats_dict.values())
    overall_vars_mean = (
        sum(s["vars_mean"] * s["n"] for s in stats_dict.values()) / total_n
    )
    overall_atoms_mean = (
        sum(s["atoms_mean"] * s["n"] for s in stats_dict.values()) / total_n
    )

    print(
        f"{'Overall':<35} {total_n:>6} {overall_vars_mean:>18.1f} {overall_atoms_mean:>22.1f}"
    )
    print("=" * 90 + "\n")


def print_example_benchmark(
    data_dict: dict[str, list[dict]], parser: ConstraintParser = None
):
    """Print an example benchmark from each dataset showing variables and atoms."""
    print("=" * 70)
    print("Example Benchmarks (Variables and Atoms)")
    print("=" * 70)

    for dataset_name, data in data_dict.items():
        if not data:
            continue

        # Pick the first benchmark as an example
        example = data[0]

        # Extract atoms if parser is provided
        if parser is not None:
            atom_count, all_atoms = count_atoms_in_benchmark(example, parser)
        else:
            atom_count = len(example["constraints"])
            all_atoms = example["constraints"]

        # Replace newlines with spaces for display
        display_name = dataset_name.replace("\n", " ")
        print(f"\n{display_name} Dataset Example:")
        print(f"  ID: {example.get('id', 'unknown')}")
        print(f"  Number of Variables: {len(example['declarations'])}")
        print(f"  Number of Atoms: {atom_count}")

        # Show variables (declarations)
        print("\n  Variables:")
        for i, var in enumerate(example["declarations"][:3]):  # Show first 3
            print(f"    {i+1}. {var}")
        if len(example["declarations"]) > 3:
            print(f"    ... and {len(example['declarations']) - 3} more")

        # Show extracted atoms
        print("\n  Extracted Atoms:")
        for i, atom in enumerate(all_atoms[:5]):  # Show first 5 atoms
            print(f"    {i+1}. {atom}")
        if len(all_atoms) > 5:
            print(f"    ... and {len(all_atoms) - 5} more")

        print()

    print("=" * 70 + "\n")


def find_extremes(data_dict: dict[str, list[dict]], parser: ConstraintParser = None):
    """Find benchmarks with minimum and maximum variables and atoms."""
    all_benchmarks = []

    # Collect all benchmarks with their dataset name
    for dataset_name, data in data_dict.items():
        for benchmark in data:
            # Count atoms if parser is provided
            if parser is not None:
                atom_count, _ = count_atoms_in_benchmark(benchmark, parser)
            else:
                atom_count = len(benchmark["constraints"])

            all_benchmarks.append(
                {
                    "id": benchmark.get("id", "unknown"),
                    "dataset": dataset_name,
                    "num_vars": len(benchmark["declarations"]),
                    "num_atoms": atom_count,
                }
            )

    # Find extremes
    min_vars = min(all_benchmarks, key=lambda x: (x["num_vars"], x["num_atoms"]))
    max_vars = max(all_benchmarks, key=lambda x: (x["num_vars"], x["num_atoms"]))

    print("=" * 70)
    print("Extreme Cases")
    print("=" * 70)
    print("\nSmallest benchmark (least vars + atoms):")
    print(f"  ID: {min_vars['id']}")
    print(f"  Dataset: {min_vars['dataset'].replace(chr(10), ' ')}")
    print(f"  Variables: {min_vars['num_vars']}")
    print(f"  Atoms: {min_vars['num_atoms']}")

    print("\nLargest benchmark (most vars + atoms):")
    print(f"  ID: {max_vars['id']}")
    print(f"  Dataset: {max_vars['dataset'].replace(chr(10), ' ')}")
    print(f"  Variables: {max_vars['num_vars']}")
    print(f"  Atoms: {max_vars['num_atoms']}")
    print("=" * 70 + "\n")


def main():
    arg_parser = argparse.ArgumentParser(
        description="Plot benchmark statistics by dataset."
    )
    arg_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="benchmark_stats.pdf",
        help="Output file path for the figure (default: results/benchmark_stats.pdf)",
    )
    arg_parser.add_argument(
        "--atoms-log",
        type=str,
        default="atoms.log",
        help="Output file path for the atoms log (default: results/atoms.log)",
    )
    arg_parser.add_argument(
        "--figsize",
        type=float,
        nargs=2,
        default=[6, 3.5],
        metavar=("WIDTH", "HEIGHT"),
        help="Figure size in inches (default: 6 3.5)",
    )
    arg_parser.add_argument(
        "--no-atoms-log",
        action="store_true",
        help="Skip generating the atoms log file",
    )
    args = arg_parser.parse_args()

    # Determine base path (dataset directory)
    script_dir = Path(__file__).parent
    base_path = script_dir.parent

    # Create results folder inside utils
    results_dir = script_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Resolve output paths relative to results folder if not absolute
    if not Path(args.output).is_absolute():
        args.output = str(results_dir / args.output)
    if not Path(args.atoms_log).is_absolute():
        args.atoms_log = str(results_dir / args.atoms_log)

    # Initialize the constraint parser for atom extraction
    print("Initializing constraint parser...")
    constraint_parser = ConstraintParser()

    # Load all datasets (order determines bar order: LLM, Grammar, Legal)
    print("Loading benchmark datasets...")

    stats_dict = {}
    data_dict = {}

    try:
        llm_data = load_llm_constraints(base_path)
        print(f"  LLM: {len(llm_data)} benchmarks loaded, computing atom statistics...")
        stats_dict["LLM-Generated\nSynthetic Constraints"] = compute_stats(
            llm_data, constraint_parser
        )
        data_dict["LLM-Generated\nSynthetic Constraints"] = llm_data
    except FileNotFoundError as e:
        print(f"  Warning: LLM constraints not found: {e}")

    try:
        grammar_data = load_grammar_constraints(base_path)
        print(
            f"  Grammar: {len(grammar_data)} benchmarks loaded, computing atom statistics..."
        )
        stats_dict["Grammar-Sampled\nConstraints"] = compute_stats(
            grammar_data, constraint_parser
        )
        data_dict["Grammar-Sampled\nConstraints"] = grammar_data
    except FileNotFoundError as e:
        print(f"  Warning: Grammar constraints not found: {e}")

    try:
        legal_data = load_legal_constraints(base_path)
        print(
            f"  Legal: {len(legal_data)} benchmarks loaded, computing atom statistics..."
        )
        stats_dict["Legally Grounded\nConstraints"] = compute_stats(
            legal_data, constraint_parser
        )
        data_dict["Legally Grounded\nConstraints"] = legal_data
    except FileNotFoundError as e:
        print(f"  Warning: Legal constraints not found: {e}")

    if not stats_dict:
        print("Error: No benchmark data found!")
        return 1

    # Print statistics table
    print_stats_table(stats_dict)

    # Print example benchmarks
    print_example_benchmark(data_dict, constraint_parser)

    # Print extreme cases
    find_extremes(data_dict, constraint_parser)

    # Generate atoms log file
    if not args.no_atoms_log:
        atoms_log_path = Path(args.atoms_log)
        write_atoms_log(data_dict, atoms_log_path, constraint_parser)

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
