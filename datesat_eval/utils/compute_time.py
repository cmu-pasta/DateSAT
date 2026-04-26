#!/usr/bin/env python3
"""
Compute averaged execution time statistics across all runs for every
encoding type and benchmark category.  Outputs a table matching the
format of Table 1 in the paper.
"""

import csv
import json
import statistics
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
OUTPUT_PATH = SCRIPT_DIR / "results" / "averaged_times.csv"

CATEGORIES = [
    ("LLM-Synthesized", "llm_constraints"),
    ("Grammar-Sampled", "grammar_constraints"),
    ("Legally Grounded", "legal_doc_constraints"),
]

ENCODINGS = [
    ("Naive", "naive_int.json"),
    ("Epoch", "epoch_days_int.json"),
    ("Hybrid", "hybrid_int.json"),
    ("αβ", "alpha_beta_int.json"),
    ("αβ-Tab", "alpha_beta_table_int.json"),
]

METRICS = ["Solve (%)", "Median Time (s)", "Mean Time (s)", "Std Dev (s)"]


def get_run_dirs(results_dir: Path) -> list[Path]:
    runs = [d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    return sorted(runs, key=lambda d: int(d.name.split("_")[1]))


def load_run_data(results_dir: Path, encoding_file: str) -> dict:
    """
    Load data for one encoding across all runs.

    Returns dict with:
      - "solve_pct": average solve percentage across runs
      - "median": median of per-problem-averaged times (seconds)
      - "mean":   mean of per-problem-averaged times (seconds)
      - "std_dev": std dev of per-problem-averaged times (seconds)
      - "n": number of problems
      - "runs": number of valid runs
    """
    times_by_id: dict[str, list[float]] = {}
    solve_rates: list[float] = []

    for run_dir in get_run_dirs(results_dir):
        fpath = run_dir / encoding_file
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)

        total = len(data)
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
        "median": statistics.median(averaged_times) if n else 0.0,
        "mean": statistics.mean(averaged_times) if n else 0.0,
        "std_dev": statistics.stdev(averaged_times) if n > 1 else 0.0,
        "n": n,
        "runs": len(solve_rates),
    }


def fmt_pct(val: float) -> str:
    return f"{val:.2f}"


def fmt_time(val: float) -> str:
    return f"{val:.2f}"


def best_in_row(values: list[float], metric: str) -> int:
    """Return the index of the best (highest for Solve, lowest for times) value."""
    if not values:
        return -1
    if metric == "Solve (%)":
        return values.index(max(values))
    return values.index(min(values))


def main() -> int:
    OUTPUT_PATH.parent.mkdir(exist_ok=True)

    enc_labels = [label for label, _ in ENCODINGS]
    csv_header = ["Benchmark", "Metric"] + enc_labels

    csv_rows: list[list[str]] = []

    # Collect all data first: category -> encoding -> stats dict
    all_data: list[tuple[str, int, dict[str, dict]]] = []

    for display_name, cat_dir_name in CATEGORIES:
        results_dir = BASE_DIR / cat_dir_name / "results"
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

    # --- Build Rich table ---
    console = Console()
    table = Table(
        title="Evaluation of DATESAT solver strategies across DATESATBENCH",
        title_style="bold white",
        show_lines=False,
        pad_edge=True,
        padding=(0, 1),
    )

    table.add_column("Benchmark", style="bold cyan", min_width=24)
    table.add_column("Metric", style="white", min_width=18)
    for enc_label in enc_labels:
        table.add_column(enc_label, justify="right", min_width=10)

    metric_key_map = {
        "Solve (%)": "solve_pct",
        "Median Time (s)": "median",
        "Mean Time (s)": "mean",
        "Std Dev (s)": "std_dev",
    }

    for cat_idx, (display_name, n_problems, enc_data) in enumerate(all_data):
        bench_label = f"{display_name} (n={n_problems})"

        if cat_idx > 0:
            table.add_section()

        for m_idx, metric in enumerate(METRICS):
            raw_values: list[float] = []
            formatted: list[str] = []
            for enc_label in enc_labels:
                d = enc_data.get(enc_label, {})
                if not d:
                    raw_values.append(float("inf") if metric != "Solve (%)" else float("-inf"))
                    formatted.append("-")
                    continue
                val = d[metric_key_map[metric]]
                raw_values.append(val)
                if metric == "Solve (%)":
                    formatted.append(fmt_pct(val))
                else:
                    formatted.append(fmt_time(val))

            best_idx = best_in_row(raw_values, metric)

            row_label = bench_label if m_idx == 0 else ""
            metric_text = Text(metric, style="italic")

            cells: list[Text | str] = [row_label, metric_text]
            for i, val_str in enumerate(formatted):
                if i == best_idx and val_str != "-":
                    cells.append(Text(val_str, style="bold green"))
                else:
                    cells.append(val_str)

            table.add_row(*cells)

            csv_row_label = bench_label if m_idx == 0 else ""
            csv_rows.append([csv_row_label, metric] + formatted)

    console.print()
    console.print(table)

    # --- Write CSV ---
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        writer.writerows(csv_rows)

    console.print(f"\n[dim]CSV written to:[/dim] [bold]{OUTPUT_PATH}[/bold]")
    return 0


if __name__ == "__main__":
    exit(main())
