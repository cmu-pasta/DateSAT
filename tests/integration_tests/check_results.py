import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure project root is on sys.path so `datesmt` can be imported when run directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datesmt.core import Date, Period  # noqa: E402
from datesmt.symbolic_api import DateSMTBuilder as _UnifiedBuilder  # noqa: E402

# --------------------------
# Parsing helpers
# --------------------------

DATE_RE = re.compile(r"^Date\((\-?\d{1,6}),\s*(\d{1,2}),\s*(\d{1,2})\)$")
PERIOD_RE = re.compile(r"^Period\((\-?\d+),\s*(\-?\d+),\s*(\-?\d+)\)$")


def parse_date_string(date_str: str) -> Date:
    m = DATE_RE.match(date_str.strip())
    if not m:
        raise ValueError(f"Unrecognized Date format: {date_str}")
    year, month, day = map(int, m.groups())
    return Date(year, month, day)


def parse_period_string(period_str: str) -> Tuple[int, int, int]:
    m = PERIOD_RE.match(period_str.strip())
    if not m:
        raise ValueError(f"Unrecognized Period format: {period_str}")
    y, mth, d = map(int, m.groups())
    return y, mth, d


# --------------------------
# IO helpers
# --------------------------


def load_results_files(results_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(results_dir.glob("results_*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
    return records


def group_by_constraint(
    records: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rec in records:
        cid = rec.get("constraint_id")
        approach = rec.get("approach")
        if not cid or not approach:
            # Skip malformed entries
            continue
        grouped.setdefault(cid, {})[approach] = rec
    return grouped


# --------------------------
# Constraint (re)builder adapters
# --------------------------

BuilderType = Callable[..., Any]


def _try_import_builders() -> List[Tuple[BuilderType, bool]]:
    """
    Returns a prioritized list of (builder, needs_approach) callables to rebuild constraints.
    """
    candidates: List[Tuple[BuilderType, bool]] = []
    # Try constraints module
    try:
        from datesmt.integration import constraints as _C  # type: ignore

        if hasattr(_C, "build_constraint"):
            # Two signatures are supported; we’ll try both, gated by needs_approach flag
            candidates.append((_C.build_constraint, False))
            candidates.append((_C.build_constraint, True))
    except Exception:
        pass
    # Try registry module
    try:
        from datesmt.integration import registry as _R  # type: ignore

        if hasattr(_R, "build_constraint"):
            candidates.append((_R.build_constraint, False))
            candidates.append((_R.build_constraint, True))
    except Exception:
        pass
    return candidates


_BUILDERS: List[Tuple[BuilderType, bool]] = _try_import_builders()


def rebuild_constraint(
    constraint_id: str, approach: Optional[str]
) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """
    Rebuilds a constraint for the given constraint_id (and optionally approach).

    Returns:
      (solver_handle, date_vars, period_vars)

    The returned `solver_handle` can be:
      - an object with `.solver` (a z3 Solver) and maps `.date_vars` / `.period_vars`
      - or a bare z3 Solver (if builder returns tuple).

    Supported builder return types:
      - obj with attributes: solver, date_vars, period_vars
      - tuple: (solver, date_vars, period_vars)
    """
    last_err: Optional[Exception] = None

    for builder, needs_approach in _BUILDERS:
        try:
            if needs_approach and approach is not None:
                built = builder(constraint_id, approach)  # type: ignore[call-arg]
            elif not needs_approach:
                built = builder(constraint_id)  # type: ignore[call-arg]
            else:
                continue  # can't call this variant without approach

            # Normalize returns
            if isinstance(built, tuple) and len(built) == 3:
                solver_handle, date_vars, period_vars = built
                return solver_handle, dict(date_vars), dict(period_vars)
            else:
                solver_handle = built
                date_vars = getattr(built, "date_vars", None)
                period_vars = getattr(built, "period_vars", None)
                if date_vars is None or period_vars is None:
                    raise TypeError(
                        "Builder returned object missing date_vars/period_vars"
                    )
                return solver_handle, dict(date_vars), dict(period_vars)
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise RuntimeError(
            f"Could not rebuild constraint {constraint_id!r}. "
            f"No compatible builder found or all failed. Last error: {last_err}"
        )
    raise RuntimeError(
        f"Could not rebuild constraint {constraint_id!r}. No builder modules available."
    )


def _get_solver(solver_handle: Any):
    # Accept either a bare z3 Solver or an object with `.solver`
    s = getattr(solver_handle, "solver", None)
    return s if s is not None else solver_handle


# --------------------------
# Fallback: rebuild by executing stored constraint_code
# --------------------------


def rebuild_from_constraint_code_record(
    rec: Dict[str, Any]
) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    code = rec.get("constraint_code")
    approach = rec.get("approach")
    if not code or not isinstance(code, str):
        raise RuntimeError("record missing constraint_code")

    # Provide a no-arg DateSMTBuilder that binds the record's approach
    def _make_builder() -> _UnifiedBuilder:
        b = _UnifiedBuilder(approach=approach or "epoch_days")
        b.enable_smtlib_print(False)
        return b

    # Prepare execution context
    glb: Dict[str, Any] = {
        "Date": Date,
        "Period": Period,
        "DateSMTBuilder": _make_builder,
    }
    loc: Dict[str, Any] = {}

    exec(code, glb, loc)

    builder_obj = (
        loc.get("builder")
        or loc.get("result")
        or glb.get("builder")
        or glb.get("result")
    )
    if builder_obj is None:
        raise RuntimeError("constraint_code did not define builder/result")

    solver_handle = getattr(builder_obj, "solver", None)
    if solver_handle is None:
        raise RuntimeError("builder lacks solver")

    date_vars = getattr(solver_handle, "date_vars", None)
    period_vars = getattr(solver_handle, "period_vars", None)
    if date_vars is None or period_vars is None:
        raise RuntimeError("solver missing date_vars/period_vars")

    return solver_handle, dict(date_vars), dict(period_vars)


# --------------------------
# Validation logic
# --------------------------


def _bind_solution_to_solver(
    solver_handle: Any,
    date_vars: Dict[str, Any],
    period_vars: Dict[str, Any],
    solution_map: Dict[str, str],
) -> Tuple[bool, str]:
    """
    Adds constraints that fix variables to the provided concrete Date/Period values.

    Returns:
      (ok, message)
    """
    s = _get_solver(solver_handle)
    try:
        from z3 import And, IntVal  # type: ignore
    except Exception as e:
        return False, f"z3 import failed: {e}"

    # We support Date(...) and Period(...)
    for var_name, val in solution_map.items():
        val = val.strip()

        # Try Date
        d_ok = False
        try:
            d = parse_date_string(val)
            if var_name not in date_vars:
                return False, f"solution provides Date for unknown var {var_name}"
            dv = date_vars[var_name]
            # Expect dv supports (dv == Date(...)) or has months/beta; we use __eq__ if available.
            try:
                s.add(dv == d)  # type: ignore[operator]
            except Exception:
                # Fallback: bind underlying (months,beta) if exposed (alpha/beta encoding)
                # dv.months_var, dv.beta_var and EOM clamp semantics vary by solver; best-effort equality:
                alpha_o = getattr(dv, "months_var", None)
                beta_o = getattr(dv, "beta_var", None)
                if alpha_o is None or beta_o is None:
                    return (
                        False,
                        f"cannot bind Date to var {var_name}: unsupported var type",
                    )
                # Generic months-since-epoch helper might not exist here; rely on dv.__ge__/__eq__ support earlier.
                return False, f"var {var_name} does not support direct Date equality"
            d_ok = True
            continue
        except ValueError:
            pass  # not a Date(...)

        # Try Period
        try:
            y, m, dd = parse_period_string(val)
            if var_name not in period_vars:
                return False, f"solution provides Period for unknown var {var_name}"
            pv = period_vars[var_name]
            # Expect pv has Int fields years/months/days
            yrs = getattr(pv, "years", None)
            mth = getattr(pv, "months", None)
            dys = getattr(pv, "days", None)
            if yrs is None or mth is None or dys is None:
                return (
                    False,
                    f"cannot bind Period to var {var_name}: unsupported var type",
                )
            s.add(And(yrs == IntVal(y), mth == IntVal(m), dys == IntVal(dd)))
            continue
        except ValueError:
            pass

        if not d_ok:
            return False, f"unrecognized solution literal for {var_name}: {val}"

    return True, "ok"


def _write_smt2(solver_handle: Any, out_path: Path) -> None:
    s = _get_solver(solver_handle)
    try:
        smt2 = s.to_smt2()
    except Exception:
        smt2 = ""  # fallback
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(smt2)


def validate_sat_record(
    constraint_id: str, rec: Dict[str, Any], save_dir: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Rebuilds the constraint and checks if the provided sat solution satisfies it.

    Returns:
      (is_valid, message)
    """
    approach = rec.get("approach")
    solution = rec.get("solution") or {}
    if not isinstance(solution, dict) or not solution:
        return False, "missing or empty solution map"

    try:
        solver_handle, date_vars, period_vars = rebuild_constraint(
            constraint_id, approach
        )
    except Exception:
        # Fallback: rebuild by executing stored constraint_code from this record
        try:
            solver_handle, date_vars, period_vars = rebuild_from_constraint_code_record(
                rec
            )
        except Exception as e2:
            return False, f"rebuild failed: {e2}"

    ok, msg = _bind_solution_to_solver(solver_handle, date_vars, period_vars, solution)
    if not ok:
        return False, f"bind failed: {msg}"

    s = _get_solver(solver_handle)
    try:
        # Save the smt2 being checked (includes binding assertions)
        if save_dir is not None:
            out_file = save_dir / f"{constraint_id}_{approach}_sat_checked.smt2"
            _write_smt2(solver_handle, out_file)
        res = s.check()
        from z3 import sat as Z3_SAT  # type: ignore

        if res == Z3_SAT:
            return True, "model satisfies assertions"
        return False, f"solver returned {res}"
    except Exception as e:
        return False, f"solver error: {e}"


# --------------------------
# Summarization per constraint (your requested policy)
# --------------------------


def summarize_constraint(
    cid: str, approaches: Dict[str, Dict[str, Any]], save_dir: Optional[Path] = None
) -> Dict[str, Any]:
    approach_statuses: Dict[str, str] = {
        a: r.get("status", "unknown") for a, r in approaches.items()
    }
    sat_recs = {a: r for a, r in approaches.items() if r.get("status") == "sat"}
    unsat_recs = {a: r for a, r in approaches.items() if r.get("status") == "unsat"}

    # For description, pick SAT one if any, else any
    any_rec = next(iter(sat_recs.values()), next(iter(approaches.values())))
    description = any_rec.get("description")

    # Validate SAT records by actually pinning and checking
    sat_validation: Dict[str, Dict[str, Any]] = {}
    for a, r in sat_recs.items():
        ok, msg = validate_sat_record(cid, r, save_dir=save_dir)
        sat_validation[a] = {"valid": ok, "message": msg, "solution": r.get("solution")}

    # Also dump UNSAT problem encodings for traceability
    if save_dir is not None:
        for a, r in unsat_recs.items():
            try:
                solver_handle, _, _ = rebuild_constraint(cid, a)
            except Exception:
                try:
                    solver_handle, _, _ = rebuild_from_constraint_code_record(r)
                except Exception:
                    solver_handle = None
            if solver_handle is not None:
                out_file = save_dir / f"{cid}_{a}_unsat_checked.smt2"
                _write_smt2(solver_handle, out_file)

    # Decide verdicts per policy, per-approach
    # Original all-unsat consensus across ALL approaches
    all_unsat = len(approach_statuses) > 0 and all(
        s == "unsat" for s in approach_statuses.values()
    )
    # New: UNSAT consensus ignoring timeouts (treat timeouts as neutral/ignored)
    non_timeout_statuses = [s for s in approach_statuses.values() if s != "timeout"]
    unsat_consensus_ignoring_timeouts = len(non_timeout_statuses) > 0 and all(
        s == "unsat" for s in non_timeout_statuses
    )
    any_sat = bool(sat_recs)
    per_approach_verdict: Dict[str, str] = {}

    for a, status in approach_statuses.items():
        if status == "error":
            per_approach_verdict[a] = "error"
        elif status == "timeout":
            # Distinct verdict for timeouts so we can tally separately
            per_approach_verdict[a] = "timeout"
        elif status == "sat":
            vinfo = sat_validation.get(a)
            if vinfo and vinfo.get("valid"):
                per_approach_verdict[a] = "correct"
            else:
                # a sat that does not validate
                per_approach_verdict[a] = "wrong"
        elif status == "unsat":
            # Treat as correct if every non-timeout approach reported UNSAT
            per_approach_verdict[a] = (
                "correct"
                if (all_unsat or unsat_consensus_ignoring_timeouts)
                else "wrong"
            )
        else:
            per_approach_verdict[a] = "wrong"

    # Retain aggregate verdict fields for backward-compatibility
    any_error = any(s == "error" for s in approach_statuses.values())
    if any_error and not any_sat and not all_unsat:
        verdict = "error"
        unsat_consensus = False
        wrong_approaches = [a for a, v in per_approach_verdict.items() if v == "wrong"]
        might_correct_approaches = []
    elif (all_unsat or unsat_consensus_ignoring_timeouts) and not any_sat:
        verdict = "correct_unsat"
        # Expose consensus flag as true when timeouts are ignored and the rest agree on UNSAT
        unsat_consensus = True
        wrong_approaches = []
        might_correct_approaches = []
    else:
        # Aggregate to "correct" if all are correct/correct_unsat; else "wrong" if any wrong; else "correct" if at least one correct
        if all(v in ("correct",) for v in per_approach_verdict.values()):
            verdict = "correct"
        elif any(v == "wrong" for v in per_approach_verdict.values()):
            verdict = "wrong"
        else:
            verdict = "correct"
        unsat_consensus = all_unsat or unsat_consensus_ignoring_timeouts
        wrong_approaches = [a for a, v in per_approach_verdict.items() if v == "wrong"]
        might_correct_approaches = []

    return {
        "constraint_id": cid,
        "description": description,
        "approach_statuses": approach_statuses,
        "sat_validation": sat_validation,  # per-sat approach validity and messages
        "unsat_consensus": unsat_consensus,
        "verdicts_by_approach": per_approach_verdict,  # per-approach: "correct" | "wrong" | "error"
        "wrong_approaches": wrong_approaches,
        "might_correct_approaches": might_correct_approaches,
    }


# --------------------------
# Batch runner
# --------------------------


def check_results_dir(results_dir: Path) -> Dict[str, Any]:
    records = load_results_files(results_dir)
    grouped = group_by_constraint(records)

    summaries: List[Dict[str, Any]] = []
    counts_by_approach: Dict[str, Dict[str, int]] = {}
    save_dir = results_dir / "smt2_assertion"
    save_dir.mkdir(parents=True, exist_ok=True)

    for cid, approaches in sorted(grouped.items(), key=lambda kv: kv[0]):
        summary = summarize_constraint(cid, approaches, save_dir=save_dir)
        summaries.append(summary)
        per = summary.get("verdicts_by_approach", {})
        for approach, v in per.items():
            if approach not in counts_by_approach:
                counts_by_approach[approach] = {
                    "correct": 0,
                    "wrong": 0,
                    "error": 0,
                    "timeout": 0,
                }
            if v in counts_by_approach[approach]:
                counts_by_approach[approach][v] += 1

    # --------------------------
    # Metrics: constraint lines and execution time
    # --------------------------
    def _smt2_lines(fp: Optional[str]) -> int:
        if not fp:
            return 0
        p = Path(fp)
        if not p.is_absolute():
            # smtlib_file paths in results are typically repo-relative
            p = PROJECT_ROOT / p
        try:
            with p.open("r", encoding="utf-8") as f:
                # Count non-empty lines; fall back to total lines if all blank
                lines = f.readlines()
                non_empty = [ln for ln in lines if ln.strip()]
                return len(non_empty) if non_empty else len(lines)
        except Exception:
            return 0

    per_constraint_metrics: Dict[str, Dict[str, Any]] = {}
    # Per-approach accumulators
    approach_line_sum: Dict[str, int] = {}
    approach_time_sum: Dict[str, float] = {}
    approach_counts: Dict[str, int] = {}

    for cid, appr_map in grouped.items():
        entries = []
        for approach, rec in appr_map.items():
            smt_path = rec.get("smtlib_file")
            lines = _smt2_lines(smt_path)
            t = float(rec.get("execution_time") or 0.0)
            entries.append({"approach": approach, "lines": lines, "execution_time": t})
            approach_line_sum[approach] = approach_line_sum.get(approach, 0) + lines
            approach_time_sum[approach] = approach_time_sum.get(approach, 0.0) + t
            approach_counts[approach] = approach_counts.get(approach, 0) + 1

        lines_sorted = sorted(
            [{"approach": e["approach"], "lines": e["lines"]} for e in entries],
            key=lambda x: (x["lines"], x["approach"]),
        )
        time_sorted = sorted(
            [
                {"approach": e["approach"], "execution_time": e["execution_time"]}
                for e in entries
            ],
            key=lambda x: (x["execution_time"], x["approach"]),
        )

        avg_lines = (
            float(sum(e["lines"] for e in entries)) / len(entries) if entries else 0.0
        )
        avg_time = (
            float(sum(e["execution_time"] for e in entries)) / len(entries)
            if entries
            else 0.0
        )

        per_constraint_metrics[cid] = {
            "lines_by_approach": lines_sorted,
            "time_by_approach": time_sorted,
            "avg_lines": avg_lines,
            "avg_time": avg_time,
        }

    per_approach_averages = {}
    for approach, cnt in approach_counts.items():
        if cnt <= 0:
            continue
        per_approach_averages[approach] = {
            "average_lines": float(approach_line_sum.get(approach, 0)) / cnt,
            "average_time": float(approach_time_sum.get(approach, 0.0)) / cnt,
            "count": cnt,
        }

    avg_lines_sorted = sorted(
        [
            {"approach": a, "average_lines": v["average_lines"]}
            for a, v in per_approach_averages.items()
        ],
        key=lambda x: (x["average_lines"], x["approach"]),
    )
    avg_time_sorted = sorted(
        [
            {"approach": a, "average_time": v["average_time"]}
            for a, v in per_approach_averages.items()
        ],
        key=lambda x: (x["average_time"], x["approach"]),
    )

    constraints_avg_lines_sorted = sorted(
        [
            {"constraint_id": cid, "avg_lines": m["avg_lines"]}
            for cid, m in per_constraint_metrics.items()
        ],
        key=lambda x: (x["avg_lines"], x["constraint_id"]),
    )
    constraints_avg_time_sorted = sorted(
        [
            {"constraint_id": cid, "avg_time": m["avg_time"]}
            for cid, m in per_constraint_metrics.items()
        ],
        key=lambda x: (x["avg_time"], x["constraint_id"]),
    )

    return {
        "results_dir": str(results_dir),
        "constraints_checked": len(summaries),
        "counts_by_approach": counts_by_approach,
        "by_constraint": summaries,
        "metrics": {
            "per_constraint": per_constraint_metrics,
            "per_approach_averages": per_approach_averages,
            "per_approach_sorted": {
                "avg_lines_sorted": avg_lines_sorted,
                "avg_time_sorted": avg_time_sorted,
            },
            "constraints_sorted_by_avg": {
                "avg_lines_sorted": constraints_avg_lines_sorted,
                "avg_time_sorted": constraints_avg_time_sorted,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check integration test results and write a consolidated verdict (model-checked)."
    )
    parser.add_argument(
        "results_dir",
        nargs="?",
        default="results/constraint1",
        help="Path to results directory (contains results_*.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output filename (defaults to <results_dir>/checked_summary.json)",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir).resolve()
    if not results_dir.exists() or not results_dir.is_dir():
        raise SystemExit(f"Results directory not found: {results_dir}")

    summary = check_results_dir(results_dir)

    output_path = (
        Path(args.output).resolve()
        if args.output
        else results_dir / "checked_summary.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=False)

    print(f"Wrote checked summary: {output_path}")


if __name__ == "__main__":
    main()
