"""
Property-based equivalence tests between Java LocalDate.plus(java.time.Period)
and Python datetime.date + dateutil.relativedelta.

These tests validate that common calendar arithmetic semantics match across
Java's java.time and Python's datetime/dateutil for a wide range of inputs.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from datesmt_int.core import Date, Period

JAVA_DIR = Path(__file__).resolve().parents[1] / "property_tests" / "java"
JAVA_SRC = JAVA_DIR / "LocalDateGroundTruth.java"
JAVA_CLASS = JAVA_DIR / "LocalDateGroundTruth.class"


def ensure_java_available_and_compiled():
    """Ensure 'javac' and 'java' exist and compile the helper if needed.

    Skips tests if Java is not available.
    """
    if shutil.which("javac") is None or shutil.which("java") is None:
        pytest.skip(
            "Java toolchain (javac/java) not available on PATH; skipping Java equivalence checks"
        )

    if not JAVA_SRC.exists():
        pytest.skip(
            f"Java source not found at {JAVA_SRC}; skipping Java equivalence checks"
        )

    # Compile if class missing or older than source
    needs_compile = (not JAVA_CLASS.exists()) or (
        JAVA_CLASS.stat().st_mtime < JAVA_SRC.stat().st_mtime
    )
    if needs_compile:
        JAVA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["javac", "LocalDateGroundTruth.java"],
                cwd=str(JAVA_DIR),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            pytest.skip(f"Failed to compile Java helper: {e.stderr}")


def java_localdate_plus(
    year: int, month: int, day: int, y: int, m: int, d: int
) -> Date:
    """Call the Java LocalDateGroundTruth helper to compute base.plus(period)."""
    ensure_java_available_and_compiled()

    try:
        proc = subprocess.run(
            [
                "java",
                "-cp",
                str(JAVA_DIR),
                "LocalDateGroundTruth",
                str(year),
                str(month),
                str(day),
                str(y),
                str(m),
                str(d),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Java helper execution failed: {e.stderr}")

    out = proc.stdout.strip()
    y_str, m_str, d_str = out.split("-")
    return Date(int(y_str), int(m_str), int(d_str))


@settings(deadline=None, max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.integers(min_value=1900, max_value=2100),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),
    st.integers(min_value=-50, max_value=50),
    st.integers(min_value=-120, max_value=120),
    st.integers(min_value=-400, max_value=400),
)
def test_java_python_period_plus_equivalence(
    base_year, base_month, base_day, py, pm, pd
):
    """Java LocalDate.plus(Period) should match Python date + relativedelta semantics."""
    # Construct base date in Python
    # Ensure base within allowed window
    assume((base_year, base_month, base_day) >= (1900, 3, 1))
    assume((base_year, base_month, base_day) <= (2100, 2, 28))
    base_py = Date(base_year, base_month, base_day).to_python_date()

    # Compute result using Python's relativedelta
    try:
        py_result = base_py + relativedelta(years=py, months=pm, days=pd)
    except Exception:
        # If Python cannot represent the result (overflow), skip this case
        assume(False)

    # Ensure result is inside the allowed window
    assume((py_result.year, py_result.month, py_result.day) >= (1900, 3, 1))
    assume((py_result.year, py_result.month, py_result.day) <= (2100, 2, 28))

    # Compute Java result via helper
    java_result = java_localdate_plus(base_year, base_month, base_day, py, pm, pd)

    # Compare results as Dates
    assert java_result == Date.from_python_date(
        py_result
    ), f"Mismatch: base={base_py}, period=({py},{pm},{pd}), java={java_result}, python={py_result}"
