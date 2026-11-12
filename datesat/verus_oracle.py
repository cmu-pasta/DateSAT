"""
Client for the Verus oracle: the compiled executable reference semantics.

proofs/src/oracle.rs gives executable versions of the reference semantics
(semantics::Date in proofs/src/semantics.rs): date validity, ordering and
Date + Period. Each one is proved equal to its spec function whenever it answers;
it answers `none` only when a machine integer would overflow. Build it with

    cd proofs && verus src/main.rs --compile -o build/datesat-oracle

or point DATESAT_VERUS_ORACLE at a binary built elsewhere.

The client keeps one oracle process per Python process and asks one question at a
time (a blank line makes the oracle flush its answer), caching every answer.
"""

import atexit
import os
import pathlib
import subprocess
import threading
from typing import Dict, Optional, Tuple

YMD = Tuple[int, int, int]

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[1] / "proofs" / "build" / "datesat-oracle"


def oracle_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("DATESAT_VERUS_ORACLE", DEFAULT_PATH))


def oracle_available() -> bool:
    p = oracle_path()
    return p.is_file() and os.access(p, os.X_OK)


class OracleUnavailable(RuntimeError):
    """The oracle binary is missing."""


class OracleOverflow(ArithmeticError):
    """The oracle could not answer because a machine integer would overflow."""


class VerusOracle:
    def __init__(self, path: Optional[pathlib.Path] = None):
        self.path = pathlib.Path(path) if path is not None else oracle_path()
        self._proc: Optional[subprocess.Popen] = None
        self._cache: Dict[str, str] = {}
        self._lock = threading.Lock()

    def _start(self) -> subprocess.Popen:
        if self._proc is None or self._proc.poll() is not None:
            if not (self.path.is_file() and os.access(self.path, os.X_OK)):
                raise OracleUnavailable(
                    f"Verus oracle not found at {self.path}; build it with "
                    "`cd proofs && verus src/main.rs --compile -o build/datesat-oracle` "
                    "or set DATESAT_VERUS_ORACLE"
                )
            self._proc = subprocess.Popen(
                [str(self.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
            )
        return self._proc

    def ask(self, request: str) -> str:
        """Send one protocol request (e.g. "lt 2024 1 1 2024 1 2") and return the answer."""
        with self._lock:
            if request in self._cache:
                return self._cache[request]
            proc = self._start()
            proc.stdin.write(request + "\n\n")
            proc.stdin.flush()
            answer = proc.stdout.readline()
            if not answer:
                err = proc.stderr.read() if proc.poll() is not None else ""
                self._proc = None
                raise RuntimeError(f"Verus oracle failed on {request!r}: {err[-2000:]}")
            answer = answer.strip()
            self._cache[request] = answer
            return answer

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)
        self._proc = None

    # ── The reference semantics ────────────────────────────────────────────

    def is_valid(self, y: int, m: int, d: int) -> bool:
        return self._bool(self.ask(f"valid {y} {m} {d}"))

    def lt(self, a: YMD, b: YMD) -> bool:
        return self._bool(self.ask(f"lt {a[0]} {a[1]} {a[2]} {b[0]} {b[1]} {b[2]}"))

    def add_period(self, a: YMD, years: int, months: int, days: int) -> YMD:
        answer = self.ask(f"add_period {a[0]} {a[1]} {a[2]} {years} {months} {days}")
        if answer == "none":
            raise OracleOverflow(f"Verus oracle overflow: {a} + Period({years}, {months}, {days})")
        y, m, d = (int(x) for x in answer.split())
        return (y, m, d)

    @staticmethod
    def _bool(answer: str) -> bool:
        if answer == "none":
            raise OracleOverflow("Verus oracle overflow")
        if answer not in ("true", "false"):
            raise RuntimeError(f"unexpected Verus oracle answer: {answer!r}")
        return answer == "true"


_shared: Optional[VerusOracle] = None


def shared_oracle() -> VerusOracle:
    """The process-wide oracle client."""
    global _shared
    if _shared is None or _shared.path != oracle_path():
        if _shared is not None:
            _shared.close()
        _shared = VerusOracle()
    return _shared


@atexit.register
def _close_shared() -> None:
    if _shared is not None:
        try:
            _shared.close()
        except Exception:
            pass
