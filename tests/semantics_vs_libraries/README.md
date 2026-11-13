# Reference semantics vs date libraries

The Verus proofs in [`proofs/`](../../proofs) show that the encodings are
equisatisfiable with a *reference* date semantics (`Date` in
`semantics.rs`). Nothing proves that the reference semantics describes the real
calendar. This directory checks it against Python's `datetime`/`dateutil` and
`java.time`, through a **Verus-verified executable oracle**. It also checks
`reference_eval.py`, the Python port of the semantics that the differential tests
([`tests/differential/`](../differential)) evaluate models with, against the same oracle.

```
cd proofs && verus src/main.rs --compile -o build/datesat-oracle   # once
pytest tests/semantics_vs_libraries -n auto
```

The oracle is [`proofs/src/oracle.rs`](../../proofs/src/oracle.rs). Each function is
proved equal to its spec function whenever it returns `Some`; it returns `None`
only on `i64` overflow, and every test asserts that it never does. Only the
line-parsing driver is unverified. Set `DATESAT_VERUS_ORACLE` to use a binary built
elsewhere. Tests skip when the oracle (or `java`, for the java.time checks) is
missing. The whole directory takes about 3 minutes on 8 workers. Every test is
marked `semantics_vs_libraries`.

| File | Role |
|------|------|
| [`oracles.py`](oracles.py) | Clients for the Verus oracle and the java.time oracle (same line protocol) |
| [`JavaTimeOracle.java`](JavaTimeOracle.java) | java.time behind that protocol, run with the `java` source launcher |
| [`test_reference_vs_libraries.py`](test_reference_vs_libraries.py) | Reference semantics vs Python `datetime`/`relativedelta` and `java.time` |
| [`test_reference_eval.py`](test_reference_eval.py) | `reference_eval.py` (used by the differential tests) vs the Verus spec |

## 1. Is the reference semantics the calendar?

The oracle is compared with two independent implementations of the proleptic
Gregorian calendar: Python's `datetime` with `dateutil.relativedelta`, and
`java.time`. Each spec function is matched to the library operation it should mean:

| Spec function | Library meaning |
|---|---|
| `is_valid(y, m, d)` | `datetime.date(y, m, d)` / `LocalDate.of(y, m, d)` accepts it |
| `lt` | date ordering |
| `EpochDelta::from_simple_date` | days since 2000-03-01 |
| `add_days(n)` | date + n days |
| `add_months(n)` | `+ relativedelta(months=n)` / `plusMonths(n)` |
| `add_period(y, m, d)` | `+ relativedelta(years=y, months=m, days=d)` / `plus(Period.of(y, m, d))` |

Within Python's range, years 1..9999 (the domain of the DateSAT solvers and the
evaluation), both libraries are compared with the oracle:

* **Exhaustive:**
  * validity of every `(y, m, d)` with `m` in 0..13 and `d` in 0..32 (4,619,538 triples);
  * for every one of the 3,652,059 valid dates: `from_simple_date`, `add_days(±1)`,
    and `lt` against the next day and against itself;
  * `leap` and `dim` for every year and month;
  * `add_months` for every (year, month) on days 1, 15 and 28..31 (where clamping
    applies), with 16 month steps up to ±100 years (10,437,744 cases).
* **Structured `add_period`:** 26 special years (centuries, 400-year multiples, leap
  years, range edges), every month, on the first, middle and last days, against a
  grid of 640 periods mixing zero and non-zero components (708,240 cases).
* **Random:** 295,514 `add_period` cases (components up to ±500 years, ±6000 months,
  ±200,000 days), 200,000 `add_days` cases (up to the full range), 350,000 `lt` pairs.
* `EpochDelta::to_ymd` (that is, `EPOCH.add_days(delta)`) on about 1,500 sampled deltas,
  including both range ends.

When a library cannot represent a result because it leaves years 1..9999, the test
requires the oracle's result to be outside that range too. Cases where
`relativedelta`'s years-and-months midpoint leaves its range are skipped, since the
spec has no range and could still end inside it.

**Beyond Python's range**, years −50,000..50,000, the oracle is compared with
`java.time` alone:
* validity of every `(y, m, d)` grid triple for 3,000+ random years, including 0 and
  negative years;
* 200,000 random dates for `from_simple_date` and `lt`;
* 200,000 random `add_period` cases and 100,000 random `add_months` cases.

**Result:** the reference semantics agrees with both libraries on every case.

What this shows: the reference semantics is the proleptic Gregorian calendar, and `add_period`
follows the add-years-and-months, clamp-to-end-of-month, then add-days convention
of `relativedelta` and `java.time`. Other libraries use other conventions, for
example not clamping, which sends Jan 31 + 1 month to early March. This is
validation by testing, not a proof: the libraries are trusted, `add_period` is
sampled rather than exhaustive, and nothing outside years −50,000..50,000 is checked.

## 2. Is `reference_eval.py` the Verus spec?

[`tests/differential/`](../differential) checks every solver model with
`reference_eval.py`, a hand transcription of the Verus spec. It is compared with the
oracle:
* `leap` and `dim`: every year in −1200..10400 and every month.
* `is_valid`: every year, every month 0..13, and the days where validity can change.
* `lt`, `add_months` and `add_period`: structured and random cases.

**Result:** `reference_eval.py` agrees with the Verus spec on every case. Injecting a
bug (an off-by-one in its `add_days`) makes these tests fail.

## The trust chain, with this directory

```
reference semantics ≈ calendar        datetime + java.time, exhaustive/structured/random   (here, part 1)
encodings ≡ reference semantics       Verus                                               (proofs/)
reference_eval.py ≡ Verus spec        Verus oracle, exhaustive on the key functions        (here, part 2)
implementation                        unit tests and differential tests                   (tests/unit_tests/, tests/differential/)
```

What remains trusted: Verus, Z3, the oracle's line driver, `datetime`/`relativedelta`
and `java.time` (as oracles of the calendar). The Python implementation of the
encodings is tested, not proved. All of this holds within the
implementation's domain of years 1..9999, plus the java.time checks beyond it.
