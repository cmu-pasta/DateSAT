#!/usr/bin/env python3
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Allow overriding site output directory via env for GitHub Pages on dev
SITE_DIR = Path(os.environ.get("COVERAGE_SITE_DIR", REPO_ROOT / "documentation" / "coverage"))
DOCS_DIR = SITE_DIR if SITE_DIR.is_absolute() else REPO_ROOT / SITE_DIR
HTML_DIR = DOCS_DIR / "coverage_html"
XML_PATH = DOCS_DIR / "coverage.xml"
INDEX_HTML = DOCS_DIR / "index.html"


def run_tests_with_coverage() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--maxfail=1",
        "--disable-warnings",
        "--color=yes",
        "--cov=datesmt",
        "--cov-branch",
        f"--cov-report=xml:{XML_PATH}",
        f"--cov-report=html:{HTML_DIR}",
        "tests/unit_tests",
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print("Tests failed. Coverage site will still be generated if XML exists.")


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_cobertura(xml_path: Path):
    if not xml_path.exists():
        raise FileNotFoundError(f"Coverage XML not found at {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Global totals
    line_rate = _safe_float(root.attrib.get("line-rate", "0"))
    branch_rate = _safe_float(root.attrib.get("branch-rate", "0"))
    lines_valid = int(float(root.attrib.get("lines-valid", 0))) if root.attrib.get("lines-valid") else 0
    lines_covered = int(float(root.attrib.get("lines-covered", 0))) if root.attrib.get("lines-covered") else 0
    branches_valid = int(float(root.attrib.get("branches-valid", 0))) if root.attrib.get("branches-valid") else 0
    branches_covered = int(float(root.attrib.get("branches-covered", 0))) if root.attrib.get("branches-covered") else 0

    totals = {
        "line_rate": line_rate,
        "branch_rate": branch_rate,
        "lines_valid": lines_valid,
        "lines_covered": lines_covered,
        "lines_missed": max(lines_valid - lines_covered, 0) if lines_valid else None,
        "branches_valid": branches_valid,
        "branches_covered": branches_covered,
        "branches_missed": max(branches_valid - branches_covered, 0) if branches_valid else None,
    }

    # Per-file aggregation grouped as module names like datesmt.core
    packages = {}
    for cls in root.findall('.//class'):
        filename = cls.attrib.get('filename', '')
        if not filename or not filename.endswith('.py'):
            continue
        # Expect paths like datesmt/core.py
        module = filename.replace(os.sep, "/").replace('/', '.')
        if module.endswith('.py'):
            module = module[:-3]
        element = module

        # Sum lines and branches from <lines><line .../>
        lines_node = cls.find('lines')
        lines_valid_local = 0
        lines_covered_local = 0
        branches_valid_local = 0
        branches_covered_local = 0
        if lines_node is not None:
            for line in lines_node.findall('line'):
                hits = int(line.attrib.get('hits', '0'))
                lines_valid_local += 1
                if hits > 0:
                    lines_covered_local += 1
                if 'branch' in line.attrib and line.attrib.get('branch') == 'true':
                    condition_coverage = line.attrib.get('condition-coverage', '')
                    try:
                        inside = condition_coverage.split('(')[1].split(')')[0]
                        covered, total = inside.split('/')
                        branches_covered_local += int(covered)
                        branches_valid_local += int(total)
                    except Exception:
                        pass

        data = packages.setdefault(element, {
            'lines_valid': 0,
            'lines_covered': 0,
            'branches_valid': 0,
            'branches_covered': 0,
        })
        data['lines_valid'] += lines_valid_local
        data['lines_covered'] += lines_covered_local
        data['branches_valid'] += branches_valid_local
        data['branches_covered'] += branches_covered_local

    rows = []
    for name, d in sorted(packages.items()):
        lv = d['lines_valid']
        lc = d['lines_covered']
        bv = d['branches_valid']
        bc = d['branches_covered']
        rows.append({
            'name': name,
            'lines_valid': lv,
            'lines_missed': max(lv - lc, 0) if lv else None,
            'line_rate': (lc / lv) if lv else 0.0,
            'branches_valid': bv,
            'branches_missed': max(bv - bc, 0) if bv else None,
            'branch_rate': (bc / bv) if bv else 0.0,
        })

    return totals, rows


def fmt_pct(x: float) -> str:
    return f"{x*100:.0f}%" if x is not None else "-"


def build_index_html(totals, rows) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = []
    html.append("<!doctype html>")
    html.append("<html lang='en'>")
    html.append("<head>")
    html.append("<meta charset='utf-8'>")
    html.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    html.append("<title>DATE-SMT Coverage</title>")
    html.append("<style>body{font-family:Arial,Helvetica,sans-serif;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f5f5f5}tr:hover{background:#fafafa}.small{color:#666;font-size:12px}.right{text-align:right}.green{color:#22863a}.red{color:#d73a49}.link{margin:12px 0}</style>")
    html.append("</head><body>")
    html.append("<h2>DATE-SMT Test Coverage</h2>")
    html.append(f"<div class='small'>Generated: {now}</div>")
    html.append("<div class='link'><a href='coverage_html/index.html'>Open detailed HTML coverage report</a></div>")

    html.append("<table>")
    html.append("<tr><th>Element</th><th>Missed Instructions</th><th>Cov.</th><th>Missed Branches</th><th>Cov.</th><th>Lines</th><th>Branches</th></tr>")

    tot_line_rate = totals.get('line_rate') or 0.0
    tot_branch_rate = totals.get('branch_rate') or 0.0
    lines_valid = totals.get('lines_valid') or 0
    lines_missed = totals.get('lines_missed')
    branches_valid = totals.get('branches_valid') or 0
    branches_missed = totals.get('branches_missed')
    html.append(
        f"<tr><td><b>Total</b></td>"
        f"<td class='right'>{lines_missed if lines_missed is not None else '-'}</td>"
        f"<td class='right'>{fmt_pct(tot_line_rate)}</td>"
        f"<td class='right'>{branches_missed if branches_missed is not None else '-'}</td>"
        f"<td class='right'>{fmt_pct(tot_branch_rate)}</td>"
        f"<td class='right'>{lines_valid}</td>"
        f"<td class='right'>{branches_valid}</td>"
        f"</tr>"
    )

    for row in rows:
        html.append(
            f"<tr>"
            f"<td>{row['name']}</td>"
            f"<td class='right'>{row['lines_missed'] if row['lines_missed'] is not None else '-'}</td>"
            f"<td class='right'>{fmt_pct(row['line_rate'])}</td>"
            f"<td class='right'>{row['branches_missed'] if row['branches_missed'] is not None else '-'}</td>"
            f"<td class='right'>{fmt_pct(row['branch_rate'])}</td>"
            f"<td class='right'>{row['lines_valid']}</td>"
            f"<td class='right'>{row['branches_valid']}</td>"
            f"</tr>"
        )

    html.append("</table>")
    html.append("<p class='small'>Created with coverage.py and pytest-cov.</p>")
    html.append("</body></html>")

    INDEX_HTML.write_text("\n".join(html), encoding="utf-8")
    print(f"Wrote {INDEX_HTML}")


def main() -> int:
    run_tests_with_coverage()
    try:
        totals, rows = parse_cobertura(XML_PATH)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    build_index_html(totals, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
