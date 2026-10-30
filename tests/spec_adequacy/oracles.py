"""
Clients for the two oracles that speak the line protocol of proofs/src/oracle.rs.

  * VerusOracle: the compiled Verus executables. Each function is proved to equal
    the corresponding reference spec function whenever it answers (it answers
    `none` only on machine-integer overflow). Build it with

        cd proofs && verus src/main.rs --compile -o build/datesat-oracle

    or point DATESAT_VERUS_ORACLE at a binary built elsewhere.
  * JavaTimeOracle: java.time, an independent implementation of the proleptic
    Gregorian calendar whose range goes far beyond Python's years 1..9999.

Tests that need an oracle skip when it is unavailable.
"""

import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
VERUS_ORACLE = pathlib.Path(os.environ.get("DATESAT_VERUS_ORACLE", ROOT / "proofs/build/datesat-oracle"))
JAVA_ORACLE_SRC = pathlib.Path(__file__).with_name("JavaTimeOracle.java")


def _run(cmd, requests):
    out = subprocess.run(cmd, input="\n".join(requests) + "\n", capture_output=True, text=True, check=True)
    answers = out.stdout.splitlines()
    assert len(answers) == len(requests), (len(answers), len(requests), out.stderr[-2000:])
    return answers


def verus(requests):
    """Answer protocol requests (e.g. "add_days 2024 2 28 1") with the Verus oracle."""
    if not VERUS_ORACLE.exists():
        pytest.skip(f"Verus oracle not built: {VERUS_ORACLE} (see tests/spec_adequacy/README.md)")
    return _run([str(VERUS_ORACLE)], requests)


def java(requests):
    """Answer protocol requests with java.time."""
    if shutil.which("java") is None:
        pytest.skip("java not installed")
    return _run(["java", str(JAVA_ORACLE_SRC)], requests)


def date_answer(s):
    """Parse a date answer ("y m d") into a tuple; None for `none`."""
    return None if s == "none" else tuple(int(x) for x in s.split())


def req(op, *args):
    return " ".join([op, *map(str, args)])
