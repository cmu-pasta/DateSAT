#!/usr/bin/env python3
"""
Run DateSATBench constraints through the enumeration baseline (brute-force solver).

``datesatbench/run_benchmarks.py`` only exercises Z3-backed approaches. This script
writes ``enumeration_baseline.json`` in the same shape as other result files so
``datesatbench.utils.validation.check_results_dir`` can consume it next to e.g.
``epoch_days_int.json``.

Usage (activate your conda env first)::

    conda activate datesmt
    python scripts/run_benchmarks_enumeration.py --datesatbenchs llm

Or run one file explicitly::

    conda activate datesmt
    python scripts/run_benchmarks_enumeration.py \\
        --constraints-file datesatbench/llm_constraints/constraints/constraints.json \\
        --output-dir datesatbench/llm_constraints/results

Enumeration does not support ``bool`` variables (no ``add_bool_var`` on
``EnumerationSolver``); those constraints are recorded with status
``not_applicable``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DATE_SAT_BENCH = Path(__file__).resolve().parent.parent / "datesatbench"


def _load_constraints(constraints_file: str) -> list[dict]:
    """Load constraints from JSON or JSONL (same behavior as run_benchmarks)."""
    path = Path(constraints_file)
    if path.suffix == ".jsonl":
        constraints: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    constraints.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: Skipping invalid JSON on line {line_num} of {path}: {e}"
                    )
        return constraints
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    return data


def _merge_solution(builder, solve_out: dict) -> dict | None:
    """Build solution map compatible with run_benchmarks / validation."""
    merged: dict[str, object] = {}
    dates = solve_out.get("dates") or {}
    for name, d in dates.items():
        merged[name] = str(d)
    for name, v in getattr(builder, "component_vars", {}).items():
        val = v.get_value()
        if val is not None:
            merged[name] = val
    return merged if merged else None


def run_constraint_enumeration(
    constraint_data: dict,
    timeout_ms: int,
    verbose: bool,
) -> dict:
    from datesat.constraint_parser import ConstraintParser
    from datesat.enumeration_baseline import EnumerationSolver

    constraint_id = constraint_data.get("id", "unknown")
    if verbose:
        print(f"\n=== Enumeration baseline: {constraint_id} ===")

    result: dict = {
        "id": constraint_id,
        "constraints": constraint_data.get("constraints", []),
        "declarations": constraint_data.get("declarations", []),
        "coverage_tags": constraint_data.get("coverage_tags", []),
        "approach": "enumeration",
        "implementation": "baseline",
        "status": "error",
        "execution_time": 0.0,
        "error_message": None,
        "solution": None,
    }

    parser = ConstraintParser()
    try:
        code = parser.parse_constraint_data(constraint_data)
    except ValueError as e:
        result["status"] = "not_applicable"
        result["error_message"] = str(e)
        if verbose:
            print(f"  not_applicable (parse): {e}")
        return result

    solver = EnumerationSolver(timeout_ms=timeout_ms)
    g = solver.get_execution_context()
    try:
        exec(code, g)
    except AttributeError as e:
        msg = str(e)
        if "add_bool_var" in msg:
            result["status"] = "not_applicable"
            result["error_message"] = msg
            if verbose:
                print(f"  not_applicable (bool vars): {msg}")
            return result
        result["status"] = "error"
        result["error_message"] = msg
        if verbose:
            print(f"  error: {msg}")
        return result
    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)
        if verbose:
            print(f"  error: {e}")
        return result

    builder = g.get("result") or g.get("builder")
    if builder is None:
        result["error_message"] = "No builder in executed constraint code"
        if verbose:
            print("  error: missing builder")
        return result

    t0 = time.time()
    try:
        out = builder.solve()
    except TimeoutError as e:
        result["status"] = "timeout"
        result["error_message"] = str(e)
        result["execution_time"] = time.time() - t0
        if verbose:
            print("  timeout")
        return result
    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)
        result["execution_time"] = time.time() - t0
        if verbose:
            print(f"  error: {e}")
        return result

    result["execution_time"] = time.time() - t0
    result["status"] = out.get("status", "error")
    if result["status"] == "sat":
        result["solution"] = _merge_solution(builder, out)
        if verbose and result["solution"]:
            for k, v in result["solution"].items():
                print(f"  {k} = {v}")
    elif verbose:
        if result["status"] == "unsat":
            print("  unsat")
        else:
            print(f"  status: {result['status']}")

    return result


def run_enumeration_file(
    constraints_file: str,
    output_dir: str,
    timeout_ms: int,
    verbose: bool,
    constraint_ids: set[str] | None,
) -> list[dict]:
    constraints = _load_constraints(constraints_file)
    if constraint_ids is not None:
        constraints = [c for c in constraints if c.get("id") in constraint_ids]
    print(f"Loaded {len(constraints)} constraints from {constraints_file}")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for c in constraints:
        results.append(run_constraint_enumeration(c, timeout_ms, verbose))

    output_file = out_path / "enumeration_baseline.json"
    output_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nResults saved to: {output_file}")

    total = len(results)
    sat = sum(1 for r in results if r["status"] == "sat")
    unsat = sum(1 for r in results if r["status"] == "unsat")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    na = sum(1 for r in results if r["status"] == "not_applicable")
    err = sum(1 for r in results if r["status"] == "error")
    avg_time = sum(r["execution_time"] for r in results) / total if total else 0.0
    print("\nSummary (enumeration baseline):")
    print(f"  sat: {sat}, unsat: {unsat}, timeout: {timeout}, not_applicable: {na}, error: {err}")
    print(f"  Avg time: {avg_time:.4f}s")
    return results


def main() -> None:
    constraint_sets = [
        {
            "name": "LLM Generated Constraints",
            "constraints_file": DATE_SAT_BENCH
            / "llm_constraints"
            / "constraints"
            / "constraints.json",
            "output_dir": DATE_SAT_BENCH / "llm_constraints" / "results",
        },
        {
            "name": "Grammar Constraints",
            "constraints_file": DATE_SAT_BENCH
            / "grammar_constraints"
            / "constraints"
            / "constraints.json",
            "output_dir": DATE_SAT_BENCH / "grammar_constraints" / "results",
        },
        {
            "name": "Legal Document Constraints",
            "constraints_file": DATE_SAT_BENCH
            / "legal_doc_constraints"
            / "constraints"
            / "constraints.jsonl",
            "output_dir": DATE_SAT_BENCH / "legal_doc_constraints" / "results",
        },
    ]

    parser = argparse.ArgumentParser(
        description="Run DateSATBench constraints with the enumeration baseline solver.",
        epilog="Tip: use `conda activate datesmt` before running this script.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60000,
        help="Timeout in milliseconds per constraint (default: 60000)",
    )
    parser.add_argument(
        "--datesatbenchs",
        nargs="+",
        default=None,
        help="Benchmark presets: llm, grammar, legal (default: all that exist)",
    )
    parser.add_argument(
        "--constraints-file",
        type=str,
        default=None,
        help="Path to constraints.json or .jsonl (overrides preset runs if set)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for enumeration_baseline.json (required with --constraints-file)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help="Only run constraints with these ids",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip check_results_dir summary after each benchmark output dir",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less per-constraint logging",
    )
    args = parser.parse_args()

    name_map = {
        "legal": "Legal Document Constraints",
        "llm": "LLM Generated Constraints",
        "grammar": "Grammar Constraints",
    }

    constraint_ids = set(args.ids) if args.ids else None

    if args.constraints_file:
        if not args.output_dir:
            parser.error("--output-dir is required when using --constraints-file")
        run_enumeration_file(
            args.constraints_file,
            args.output_dir,
            args.timeout,
            verbose=not args.quiet,
            constraint_ids=constraint_ids,
        )
        if not args.no_analysis:
            _maybe_analyze(Path(args.output_dir))
        return

    selected = constraint_sets
    if args.datesatbenchs:
        mapped = []
        for ds in args.datesatbenchs:
            if ds.lower() in name_map:
                mapped.append(name_map[ds.lower()])
            elif ds in name_map.values():
                mapped.append(ds)
            else:
                print(f"Warning: Unknown benchmark name: {ds}")
        selected = [cs for cs in constraint_sets if cs["name"] in mapped]
        if not selected:
            print("No matching benchmarks. Use: llm, grammar, legal")
            sys.exit(1)

    for cs in selected:
        cfile = cs["constraints_file"]
        odir = cs["output_dir"]
        print("=" * 70)
        print(cs["name"])
        print("=" * 70)
        if not cfile.exists():
            print(f"Skipping — not found: {cfile}\n")
            continue
        run_enumeration_file(
            str(cfile),
            str(odir),
            args.timeout,
            verbose=not args.quiet,
            constraint_ids=constraint_ids,
        )
        if not args.no_analysis:
            _maybe_analyze(odir)
        print()


def _maybe_analyze(results_dir: Path) -> None:
    try:
        from datesatbench.utils.validation import check_results_dir
    except ImportError as e:
        print(f"Skipping analysis (import failed): {e}")
        return

    print("Running validation summary (check_results_dir)…")
    summary = check_results_dir(results_dir, enumeration_filter=None)
    out = results_dir / "checked_summary_enumeration_run.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Analysis saved to: {out}")


if __name__ == "__main__":
    main()
