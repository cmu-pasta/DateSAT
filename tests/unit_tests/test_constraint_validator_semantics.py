"""Which semantics the validator uses for date operations.

With semantics="verus" every date operation (validity, ordering, Date + Period,
including on Date literals) must be answered by the Verus oracle, the executable
reference semantics. A stub oracle that answers wrongly on purpose shows that the
oracle's answer, not datesat.core.Date's, decides the verdict.
"""

import random
import stat
import sys
import textwrap

import pytest

from datesat import constraint_validator, verus_oracle
from datesat.constraint_validator import validate_constraint_solution, validation_semantics
from datesat.core import Date, Period


def _code(date_vars, *constraints):
    lines = ["builder = DateSATBuilder()"]
    lines += [f'{v} = builder.add_date_var("{v}")' for v in date_vars]
    lines += [f"builder.add_constraint({c})" for c in constraints]
    return "\n".join(lines) + "\n"


@pytest.fixture
def stub_oracle(tmp_path, monkeypatch):
    """An oracle that says every date is valid, nothing is before anything, and every
    Date + Period is 2000-01-01."""
    path = tmp_path / "stub-oracle"
    path.write_text(f"#!{sys.executable}\n" + textwrap.dedent("""
        import sys
        for line in sys.stdin:
            op = line.split()[:1]
            if not op:
                sys.stdout.flush()
            elif op[0] == "valid":
                print("true")
            elif op[0] == "lt":
                print("false")
            elif op[0] == "add_period":
                print("2000 1 1")
            else:
                print("none")
    """))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DATESAT_VERUS_ORACLE", str(path))
    return path


def test_oracle_decides_ordering(stub_oracle):
    code = _code(["D0"], "D0 < Date(2024, 1, 2)")
    model = {"D0": "Date(2024, 1, 1)"}
    assert validate_constraint_solution(code, model, semantics="python")[0]
    assert not validate_constraint_solution(code, model, semantics="verus")[0]


def test_oracle_decides_date_plus_period(stub_oracle):
    code = _code(["D0"], "D0 + Period(0, 1, 0) == Date(2000, 1, 1)")
    model = {"D0": "Date(2024, 1, 31)"}
    assert not validate_constraint_solution(code, model, semantics="python")[0]
    assert validate_constraint_solution(code, model, semantics="verus")[0]


def test_oracle_decides_on_date_literals(stub_oracle):
    # No variable involved: the literal arithmetic and comparison go to the oracle too.
    code = _code([], "Date(2024, 1, 31) + Period(0, 1, 0) == Date(2000, 1, 1)",
                 "Not(Date(2024, 1, 1) < Date(2025, 1, 1))")
    assert not validate_constraint_solution(code, {}, semantics="python")[0]
    assert validate_constraint_solution(code, {}, semantics="verus")[0]


def test_disagreement_on_validity_is_reported(stub_oracle):
    # The stub accepts 2023-02-29; datesat.core.Date cannot hold it.
    ok, msg = validate_constraint_solution(_code(["D0"], "D0 == D0"), {"D0": "Date(2023, 2, 29)"},
                                           semantics="verus")
    assert not ok


def test_verus_requires_the_oracle(tmp_path, monkeypatch):
    monkeypatch.setenv("DATESAT_VERUS_ORACLE", str(tmp_path / "missing"))
    with pytest.raises(verus_oracle.OracleUnavailable):
        validate_constraint_solution(_code(["D0"], "D0 == D0"), {"D0": "Date(2024, 1, 1)"},
                                     semantics="verus")


def test_auto_falls_back_to_python_with_a_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("DATESAT_VERUS_ORACLE", str(tmp_path / "missing"))
    monkeypatch.setattr(constraint_validator, "_warned_fallback", False)
    with pytest.warns(UserWarning, match="Verus oracle not built"):
        assert validation_semantics("auto") == "python"
    assert validate_constraint_solution(_code(["D0"], "D0 < Date(2024, 1, 2)"),
                                        {"D0": "Date(2024, 1, 1)"}, semantics="auto")[0]


def test_semantics_from_environment(stub_oracle, monkeypatch):
    monkeypatch.setenv("DATESAT_VALIDATION_SEMANTICS", "python")
    assert validation_semantics() == "python"
    monkeypatch.setenv("DATESAT_VALIDATION_SEMANTICS", "verus")
    assert validation_semantics() == "verus"


def test_unknown_semantics():
    with pytest.raises(ValueError):
        validation_semantics("java")


# ── The real oracle ─────────────────────────────────────────────────────────

needs_oracle = pytest.mark.skipif(not verus_oracle.oracle_available(),
                                  reason="Verus oracle not built (see datesat/verus_oracle.py)")


def _random_date(rng):
    y = rng.choice([rng.randint(-3000, 12000), rng.choice([0, 1, 4, 100, 400, 1900, 2000, 9999])])
    m = rng.randint(1, 12)
    d = rng.choice([1, 15, 28, 29, 30, 31])
    try:
        return Date(y, m, d)
    except ValueError:
        return Date(y, m, 28)


@needs_oracle
def test_real_oracle_agrees_with_python_on_random_models():
    rng = random.Random(0)
    for _ in range(300):
        a, b = _random_date(rng), _random_date(rng)
        p = Period(rng.randint(-500, 500), rng.randint(-30, 30), rng.randint(-100_000, 100_000))
        r = a + p
        code = _code(["D0", "D1", "D2"],
                     f"D0 + Period({p.years}, {p.months}, {p.days}) == D2",
                     "D0 < D1" if a < b else "D0 >= D1")
        model = {"D0": str(a), "D1": str(b), "D2": str(r)}
        for semantics in ("verus", "python"):
            ok, msg = validate_constraint_solution(code, model, semantics=semantics)
            assert ok, (semantics, model, msg)


@needs_oracle
def test_real_oracle_rejects_invalid_dates():
    code = _code(["D0"], "D0 == D0")
    for bad in ("Date(2023, 2, 29)", "Date(2100, 2, 29)", "Date(2024, 4, 31)", "Date(2024, 13, 1)"):
        assert not validate_constraint_solution(code, {"D0": bad}, semantics="verus")[0]
    assert validate_constraint_solution(code, {"D0": "Date(2000, 2, 29)"}, semantics="verus")[0]


@needs_oracle
def test_real_oracle_overflow_fails_validation():
    # The oracle computes in i64 and answers `none` rather than a wrong date.
    code = _code(["D0"], f"D0 + Period({2**62}, 0, 0) > D0")
    ok, msg = validate_constraint_solution(code, {"D0": "Date(2024, 1, 1)"}, semantics="verus")
    assert not ok and "overflow" in msg
