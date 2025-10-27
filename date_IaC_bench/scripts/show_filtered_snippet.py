#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def load_hits(hits_path: Path):
    with hits_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def slice_by_lines(text: str, start_line: int, end_line: int, context: int) -> str:
    lines = text.splitlines(keepends=True)
    start_idx = max(1, start_line - context)
    end_idx = min(len(lines), end_line + context)
    return "".join(lines[start_idx - 1:end_idx])


def slice_by_bytes(data: bytes, start_byte: int, end_byte: int) -> bytes:
    start = max(0, start_byte)
    end = min(len(data), end_byte)
    return data[start:end]


def main() -> None:
    ap = argparse.ArgumentParser(description="Print the source snippet for a hit from aws_filtered.jsonl")
    ap.add_argument("--filtered-file", default="/Users/angelc2/Downloads/10173400/datesmt_bench/metadata/aws_filtered.jsonl",
                    help="Path to aws_filtered.jsonl")
    ap.add_argument("--repos-root", required=True, help="Root of repos (e.g., dataset folder)")

    # Selection options
    ap.add_argument("--sha", help="snippet_sha256 to select a single hit")
    ap.add_argument("--repo-id", help="Repo ID to filter hits")
    ap.add_argument("--rel-file", help="Relative file path inside the repo (optional with --repo-id)")
    ap.add_argument("--start-line", type=int, help="1-based start line for the hit (code span)")
    ap.add_argument("--end-line", type=int, help="1-based end line for the hit (code span)")
    ap.add_argument("--start-byte", type=int, help="Start byte offset for the hit (code span)")
    ap.add_argument("--end-byte", type=int, help="End byte offset for the hit (code span)")
    ap.add_argument("--context", type=int, default=0, help="Extra context lines when using line slicing")
    # JSONL line range selection (by filtered file line numbers)
    ap.add_argument("--filtered-start", type=int, help="1-based start line in filtered JSONL to select hits")
    ap.add_argument("--filtered-end", type=int, help="1-based end line in filtered JSONL to select hits")
    ap.add_argument("--max-matches", type=int, default=1, help="Max hits to print when filtering")
    args = ap.parse_args()

    hits_path = Path(args.filtered_file)
    repos_root = Path(args.repos_root)
    if not hits_path.exists():
        print(f"[ERROR] hits file not found: {hits_path}", file=sys.stderr)
        sys.exit(2)

    matches = []
    # Mode 1: select by snippet sha
    if args.sha:
        for hit in load_hits(hits_path):
            if hit.get("snippet_sha256") == args.sha:
                matches.append(hit)
                break
    # Mode 2: select by JSONL line range in filtered file
    elif args.filtered_start is not None and args.filtered_end is not None:
        for idx, hit in enumerate(load_hits(hits_path), start=1):
            if args.filtered_start <= idx <= args.filtered_end:
                matches.append(hit)
                if len(matches) >= args.max_matches:
                    break
    # Mode 3: filter by repo id (and optional file and spans)
    elif args.repo_id:
        for hit in load_hits(hits_path):
            if hit.get("repo_id") != args.repo_id:
                continue
            if args.rel_file and hit.get("rel_file") != args.rel_file:
                continue
            if args.start_line and args.end_line:
                s = int(hit.get("start_line", -1)); e = int(hit.get("end_line", -1))
                if not (s <= args.end_line and e >= args.start_line):
                    continue
            if args.start_byte is not None and args.end_byte is not None:
                s = int(hit.get("start_byte", -1)); e = int(hit.get("end_byte", -1))
                if not (s <= args.end_byte and e >= args.start_byte):
                    continue
            matches.append(hit)
            if len(matches) >= args.max_matches:
                break

    if not matches:
        print("[INFO] No matching hit found.")
        sys.exit(0)

    # Use the first match
    hit = matches[0]
    repo_id = hit["repo_id"]
    rel_file = hit["rel_file"]
    src_path = repos_root / repo_id / rel_file
    if not src_path.exists():
        print(f"[ERROR] source file not found: {src_path}", file=sys.stderr)
        sys.exit(2)

    # Prefer byte slicing if both provided, else line slicing
    try:
        if args.start_byte is not None and args.end_byte is not None:
            data = src_path.read_bytes()
            snippet_b = slice_by_bytes(data, args.start_byte, args.end_byte)
            try:
                print(snippet_b.decode("utf-8", errors="ignore"), end="")
            except Exception:
                # fallback to repr
                print(repr(snippet_b))
        else:
            text = src_path.read_text(encoding="utf-8", errors="ignore")
            sline = int(hit.get("start_line", 1)) if args.start_line is None else args.start_line
            eline = int(hit.get("end_line", 1)) if args.end_line is None else args.end_line
            print(slice_by_lines(text, sline, eline, args.context), end="")
    except Exception as e:
        print(f"[ERROR] failed to print snippet: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


