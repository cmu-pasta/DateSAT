#!/usr/bin/env python3
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Allow overriding site output directory via env for GitHub Pages on dev
SITE_DIR = Path(
    os.environ.get("COVERAGE_SITE_DIR", REPO_ROOT / "documentation" / "coverage")
)
DOCS_DIR = SITE_DIR if SITE_DIR.is_absolute() else REPO_ROOT / SITE_DIR
# Keep the detailed coverage report under a subdirectory for organization
HTML_DIR = DOCS_DIR / "coverage_html"
XML_PATH = DOCS_DIR / "coverage.xml"
INDEX_HTML = DOCS_DIR / "index.html"
BADGE_SVG = DOCS_DIR / "badge.svg"


def run_tests_with_coverage() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-n",
        os.environ.get("PYTEST_WORKERS", "auto"),
        "--maxfail=1",
        "--disable-warnings",
        "--color=yes",
        "--cov=datesmt_bitvector",
        "--cov=datesmt_int",
        "--cov-branch",
        f"--cov-report=xml:{XML_PATH}",
        f"--cov-report=html:{HTML_DIR}",
        # Include both unit and property tests in CI coverage
        "tests/unit_tests",
        "tests/property_tests",
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
    lines_valid = (
        int(float(root.attrib.get("lines-valid", 0)))
        if root.attrib.get("lines-valid")
        else 0
    )
    lines_covered = (
        int(float(root.attrib.get("lines-covered", 0)))
        if root.attrib.get("lines-covered")
        else 0
    )
    branches_valid = (
        int(float(root.attrib.get("branches-valid", 0)))
        if root.attrib.get("branches-valid")
        else 0
    )
    branches_covered = (
        int(float(root.attrib.get("branches-covered", 0)))
        if root.attrib.get("branches-covered")
        else 0
    )

    totals = {
        "line_rate": line_rate,
        "branch_rate": branch_rate,
        "lines_valid": lines_valid,
        "lines_covered": lines_covered,
        "lines_missed": max(lines_valid - lines_covered, 0) if lines_valid else None,
        "branches_valid": branches_valid,
        "branches_covered": branches_covered,
        "branches_missed": (
            max(branches_valid - branches_covered, 0) if branches_valid else None
        ),
    }

    # Per-file aggregation grouped as module names like datesmt_int.core
    packages = {}
    for cls in root.findall('.//class'):
        filename = cls.attrib.get('filename', '')
        if not filename or not filename.endswith('.py'):
            continue
        # Expect paths like datesmt_int/core.py
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

        data = packages.setdefault(
            element,
            {
                'lines_valid': 0,
                'lines_covered': 0,
                'branches_valid': 0,
                'branches_covered': 0,
            },
        )
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
        rows.append(
            {
                'name': name,
                'lines_valid': lv,
                'lines_missed': max(lv - lc, 0) if lv else None,
                'line_rate': (lc / lv) if lv else 0.0,
                'branches_valid': bv,
                'branches_missed': max(bv - bc, 0) if bv else None,
                'branch_rate': (bc / bv) if bv else 0.0,
            }
        )

    return totals, rows


def fmt_pct(x: float) -> str:
    return f"{x*100:.0f}%" if x is not None else "-"


def build_index_html(totals, rows) -> None:
    # Serve an embedded view of the detailed report without redirecting.
    html = []
    html.append("<!doctype html>")
    html.append("<html lang='en'>")
    html.append("<head>")
    html.append("<meta charset='utf-8'>")
    html.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    html.append("<title>DATE-SMT Coverage</title>")
    html.append(
        "<style>html,body{height:100%;margin:0}body{font-family:Arial,Helvetica,sans-serif}#wrap{height:100%;display:flex;flex-direction:column}header{padding:8px 12px;border-bottom:1px solid #eee;background:#fafafa}header a{color:#0366d6;text-decoration:none}main{flex:1}iframe{border:0;width:100%;height:100%}</style>"
    )
    html.append("</head>")
    html.append("<body>")
    html.append("<div id='wrap'>")
    html.append(
        "<header><strong>DATE-SMT Coverage</strong> — <a href='coverage_html/index.html'>open full page</a></header>"
    )
    html.append(
        "<main><iframe src='coverage_html/index.html' title='Coverage Report'></iframe></main>"
    )
    html.append("</div>")
    html.append("</body>")
    html.append("</html>")

    INDEX_HTML.write_text("\n".join(html), encoding="utf-8")
    print(f"Wrote {INDEX_HTML}")


def _extract_percent_from_html(html_index: Path):
    """
    Parse the numeric percent from coverage.py's HTML index header so the badge
    matches the displayed value exactly. Returns an int percent or None.
    """
    # Wait briefly for file to appear in case filesystem lags
    import time

    for _ in range(10):
        if html_index.exists():
            break
        time.sleep(0.2)
    try:
        text = html_index.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    import re

    # Matches "Coverage Report:61.5%" or "Coverage Report: 61.5%"
    m = re.search(r"Coverage Report\s*:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    if not m:
        return None
    try:
        return int(round(float(m.group(1))))
    except Exception:
        return None


def build_badge_svg(totals) -> None:
    """
    Create a simple Shields-style SVG badge summarizing total statement coverage.
    The badge is written to BADGE_SVG and published with the site.
    """
    # Prefer the exact headline value from the HTML report header.
    pct_from_html = _extract_percent_from_html(HTML_DIR / "index.html")
    if pct_from_html is not None:
        pct_int = pct_from_html
    else:
        # Fallback to XML line-rate (statement coverage)
        statement_rate = totals.get("line_rate") or 0.0
        pct_int = int(round(statement_rate * 100))
    value_text = f"{pct_int}%"

    # Pick a color similar to Shields.io thresholds
    if pct_int >= 90:
        color = "#4c1"  # brightgreen
    elif pct_int >= 80:
        color = "#97CA00"  # green
    elif pct_int >= 70:
        color = "#a4a61d"  # yellowgreen-ish
    elif pct_int >= 60:
        color = "#dfb317"  # yellow
    elif pct_int >= 50:
        color = "#fe7d37"  # orange
    else:
        color = "#e05d44"  # red

    label_text = "coverage"

    # Approximate text widths: ~7px per character + padding
    def approx_width(text: str) -> int:
        return 10 + 7 * len(text)

    label_width = max(50, approx_width(label_text))
    value_width = max(34, approx_width(value_text))
    total_width = label_width + value_width

    # Text centers for each section
    label_center = label_width / 2
    value_center = label_width + (value_width / 2)

    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label_text}: {value_text}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="m"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></mask>
  <g mask="url(#m)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_center}" y="15" fill="#010101" fill-opacity=".3">{label_text}</text>
    <text x="{label_center}" y="14">{label_text}</text>
    <text x="{value_center}" y="15" fill="#010101" fill-opacity=".3">{value_text}</text>
    <text x="{value_center}" y="14">{value_text}</text>
  </g>
</svg>
""".strip()

    BADGE_SVG.write_text(svg, encoding="utf-8")
    print(f"Wrote {BADGE_SVG}")


def main() -> int:
    run_tests_with_coverage()
    try:
        totals, rows = parse_cobertura(XML_PATH)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    build_index_html(totals, rows)
    build_badge_svg(totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
