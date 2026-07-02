#!/usr/bin/env python3
"""
Compute averaged execution time statistics across all runs for every
encoding type and benchmark category.  Outputs a table matching the
format of Table 1 in the paper.
"""

import argparse
import csv
import json
import statistics
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

# Category subdirectories inside a results run folder
# (e.g. eval/results/20260701_111457/{llm,grammar,legal})
CATEGORIES = [
    ("LLM-Synthesized", "llm"),
    ("Grammar-Sampled", "grammar"),
    ("Legally Grounded", "legal"),
]

ENCODINGS = [
    ("Simple", "simple_int.json"),
    ("Epoch", "epoch_days_int.json"),
    ("Hybrid-YMD", "hybrid_ymd_int.json"),
    ("Hybrid-Epoch", "hybrid_epoch_int.json"),
    ("αβ", "alpha_beta_int.json"),
    ("αβ-Tab", "alpha_beta_table_int.json"),
]

METRICS = ["Solve (%)", "Median Time (s)", "Mean Time (s)", "Std Dev (s)"]


def get_run_dirs(results_dir: Path) -> list[Path]:
    runs = [d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    if runs:
        return sorted(runs, key=lambda d: int(d.name.split("_")[1]))
    # Flat layout: encoding files live directly in the category directory
    return [results_dir]


def load_run_data(results_dir: Path, encoding_file: str) -> dict:
    """
    Load data for one encoding across all runs.

    Time statistics cover ALL problems, with timeouts contributing their recorded
    execution_time (the timeout ceiling, ~60s). This penalized (PAR-1 style)
    convention matches checked_summary_with_baseline.json and avoids survivorship
    bias: an encoding that only solves its easiest instances would otherwise get
    flattering solved-only times despite a poor solve rate.

    Returns dict with:
      - "solve_pct": average solve percentage across runs
      - "median": median of per-problem-averaged times (seconds), None if no times
      - "mean":   mean of per-problem-averaged times (seconds), None if no times
      - "std_dev": std dev of per-problem-averaged times (seconds), None if no times
      - "n": total number of problems in the benchmark
      - "runs": number of valid runs
    """
    times_by_id: dict[str, list[float]] = {}
    solve_rates: list[float] = []
    total_problems = 0

    for run_dir in get_run_dirs(results_dir):
        fpath = run_dir / encoding_file
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)

        total = len(data)
        total_problems = max(total_problems, total)
        solved = sum(1 for e in data if e.get("status") in ("sat", "unsat"))
        solve_rates.append((solved / total) * 100 if total > 0 else 0.0)

        for entry in data:
            if entry.get("execution_time") is not None:
                pid = entry.get("id", "unknown")
                times_by_id.setdefault(pid, []).append(entry["execution_time"])

    if not solve_rates:
        return {}

    averaged_times = [statistics.mean(t) for t in times_by_id.values()]
    n = len(averaged_times)

    return {
        "solve_pct": statistics.mean(solve_rates),
        "median": statistics.median(averaged_times) if n else None,
        "mean": statistics.mean(averaged_times) if n else None,
        "std_dev": (statistics.stdev(averaged_times) if n > 1 else 0.0) if n else None,
        "n": total_problems,
        "runs": len(solve_rates),
    }


def fmt_pct(val) -> str:
    return f"{val:.2f}" if val is not None else "-"


def fmt_time(val) -> str:
    return f"{val:.2f}" if val is not None else "-"


def write_pdf(display_rows: list[dict], enc_labels: list[str], output_path: Path):
    """Render the summary table to a PDF with the best value per row in bold green."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    col_labels = ["Benchmark", "Metric"] + list(enc_labels)
    cell_text = [
        [r["bench"] if r["first"] else "", r["metric"]] + r["formatted"]
        for r in display_rows
    ]

    fig_height = 0.32 * (len(cell_text) + 1) + 1.0
    fig, ax = plt.subplots(figsize=(11, fig_height))
    ax.axis("off")

    tbl = ax.table(cellText=cell_text, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.auto_set_column_width(range(len(col_labels)))

    for j in range(len(col_labels)):
        tbl[0, j].set_text_props(fontweight="bold")
        tbl[0, j].set_facecolor("#e8e8e8")
    for i, row in enumerate(display_rows, start=1):
        tbl[i, 1].set_text_props(style="italic")
        for k in row["best"]:
            tbl[i, 2 + k].set_text_props(color="#1a7f37", fontweight="bold")

    fig.suptitle(
        "Evaluation of DATESAT solver strategies across DATESATBENCH",
        fontweight="bold",
    )
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def best_indices(values: list, metric: str) -> set[int]:
    """
    Return the indices tied for the best value (highest for Solve, lowest for
    times). Comparison happens at display precision (2 decimals) so all cells
    that render identically are highlighted together. None values (missing
    encodings or no timing data) never win. Std Dev is a spread measure, not a
    performance metric (mass timeouts produce a deceptively low spread), so no
    cell is highlighted there.
    """
    if metric == "Std Dev (s)":
        return set()
    rounded = [round(v, 2) if v is not None else None for v in values]
    candidates = [r for r in rounded if r is not None]
    if not candidates:
        return set()
    best = max(candidates) if metric == "Solve (%)" else min(candidates)
    return {i for i, r in enumerate(rounded) if r == best}


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="Compute averaged execution time statistics for a results run folder."
    )
    arg_parser.add_argument(
        "results_dir",
        type=str,
        help="Path to a results run folder (e.g. eval/results/20260701_111457) "
        "containing llm/, grammar/, and legal/ subdirectories",
    )
    args = arg_parser.parse_args()

    results_root = Path(args.results_dir).expanduser().resolve()
    if not results_root.is_dir():
        print(f"Error: Results folder '{results_root}' does not exist.")
        return 1

    csv_path = results_root / "averaged_times.csv"
    pdf_path = results_root / "averaged_times.pdf"

    enc_labels = [label for label, _ in ENCODINGS]
    csv_header = ["Benchmark", "Metric"] + enc_labels

    # Collect all data first: category -> encoding -> stats dict
    all_data: list[tuple[str, int, dict[str, dict]]] = []

    for display_name, cat_dir_name in CATEGORIES:
        results_dir = results_root / cat_dir_name
        if not results_dir.is_dir():
            continue

        enc_data: dict[str, dict] = {}
        n_problems = 0
        for enc_label, enc_file in ENCODINGS:
            d = load_run_data(results_dir, enc_file)
            enc_data[enc_label] = d
            if d.get("n", 0) > n_problems:
                n_problems = d["n"]

        all_data.append((display_name, n_problems, enc_data))

    metric_key_map = {
        "Solve (%)": "solve_pct",
        "Median Time (s)": "median",
        "Mean Time (s)": "mean",
        "Std Dev (s)": "std_dev",
    }

    # --- Build rows once, shared by the terminal, CSV, and PDF output ---
    display_rows: list[dict] = []
    for display_name, n_problems, enc_data in all_data:
        bench_label = f"{display_name} (n={n_problems})"

        for m_idx, metric in enumerate(METRICS):
            raw_values: list = []
            formatted: list[str] = []
            for enc_label in enc_labels:
                d = enc_data.get(enc_label, {})
                val = d.get(metric_key_map[metric]) if d else None
                raw_values.append(val)
                if metric == "Solve (%)":
                    formatted.append(fmt_pct(val))
                else:
                    formatted.append(fmt_time(val))

            display_rows.append(
                {
                    "bench": bench_label,
                    "first": m_idx == 0,
                    "metric": metric,
                    "formatted": formatted,
                    "best": best_indices(raw_values, metric),
                }
            )

    # --- Build Rich table ---
    console = Console()
    table = Table(
        title="Evaluation of DATESAT solver strategies across DATESATBENCH",
        title_style="bold white",
        show_lines=False,
        pad_edge=True,
        padding=(0, 1),
    )

    # No fixed column widths and overflow="fold": on narrow terminals the
    # columns shrink and wrap instead of the rightmost ones being cropped away.
    table.add_column("Benchmark", style="bold cyan", overflow="fold")
    table.add_column("Metric", style="white", overflow="fold")
    for enc_label in enc_labels:
        table.add_column(enc_label, justify="right", overflow="fold")

    for row_idx, row in enumerate(display_rows):
        if row["first"] and row_idx > 0:
            table.add_section()

        cells: list[Text | str] = [
            row["bench"] if row["first"] else "",
            Text(row["metric"], style="italic"),
        ]
        for i, val_str in enumerate(row["formatted"]):
            if i in row["best"]:
                cells.append(Text(val_str, style="bold green"))
            else:
                cells.append(val_str)

        table.add_row(*cells)

    console.print()
    console.print(table)

    # --- Write CSV ---
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        writer.writerows(
            [[r["bench"] if r["first"] else "", r["metric"]] + r["formatted"] for r in display_rows]
        )

    console.print(f"\n[dim]CSV written to:[/dim] [bold]{csv_path}[/bold]")

    # --- Write PDF (always fully readable regardless of terminal width) ---
    try:
        write_pdf(display_rows, enc_labels, pdf_path)
        console.print(f"[dim]PDF written to:[/dim] [bold]{pdf_path}[/bold]")
    except ImportError:
        console.print("[yellow]matplotlib not installed; skipping PDF output[/yellow]")

    return 0


if __name__ == "__main__":
    exit(main())
