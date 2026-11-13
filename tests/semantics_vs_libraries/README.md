# Reference semantics vs date libraries

The Verus proofs in [`proofs/`](../../proofs) show that the encodings are equisatisfiable with a *reference* date semantics (`Date` in `semantics.rs`). 
Nothing proves that the reference semantics describes the real calendar. 
This directory checks it against Python's `datetime`/`dateutil` and `java.time`, through a **Verus-verified executable oracle**.

```
cd proofs && verus src/main.rs --compile -o build/datesat-oracle   # once
pytest tests/semantics_vs_libraries -m semantics_vs_libraries -n auto
```

The oracle is [`proofs/src/oracle.rs`](../../proofs/src/oracle.rs). 
Each function is proved equal to its spec function whenever it returns `Some`; 
it returns `None` only on `i64` overflow, and every test asserts that it never does. 
Only the line-parsing driver is unverified. 
Set `DATESAT_VERUS_ORACLE` to use a binary built elsewhere. 
Tests skip when the oracle (or `java`, for the java.time checks) is missing. 
The whole directory (56 tests) takes about 2 minutes on 6 workers. 
Every test is marked `semantics_vs_libraries`.

| File | Role |
|------|------|
| [`oracles.py`](oracles.py) | Clients for the Verus oracle and the java.time oracle (same line protocol) |
| [`JavaTimeOracle.java`](JavaTimeOracle.java) | java.time behind that protocol, run with the `java` source launcher |
| [`test_reference_vs_libraries.py`](test_reference_vs_libraries.py) | Reference semantics vs Python `datetime`/`relativedelta` and `java.time` |

## Is the reference semantics the calendar?

The spec functions are not executable, so the tests run the oracle. 
Verus proves that each oracle function returns the value of its spec function whenever it answers. 
A passing case `oracle(x) == library(x)` therefore establishes `spec(x) == library(x)` for that input `x`; 
what is trusted is Verus, the Rust compiler and the oracle's line-parsing driver.

The oracle is compared with two independent implementations of the proleptic Gregorian calendar: Python's `datetime` with `dateutil.relativedelta`, and `java.time`. 
Each spec function is matched to the library operation it should mean (`dateutil` is only involved in `add_months` and `add_period`; the rest is plain `datetime`). 
Verus proves them consistent with it:

| Spec function | Library meaning |
|---|---|
| `is_valid(y, m, d)` | `datetime.date(y, m, d)` / `LocalDate.of(y, m, d)` accepts it |
| `lt` | date ordering |
| `add_days(n)` | date + n days |
| `add_months(n)` | `+ relativedelta(months=n)` / `plusMonths(n)` |
| `add_period(y, m, d)` | `+ relativedelta(years=y, months=m, days=d)` / `plus(Period.of(y, m, d))` |

The oracle is compared with each library separately, over the range that library supports. 
Python's `datetime` only represents years 1..9999; `java.time` goes far beyond. 
The solvers are unbounded by default (and in the paper's evaluation), so only the `java.time` checks say anything about dates outside years 1..9999.

### Against Python (`datetime`, `dateutil`): years 1..9999 only

Every case starts from a date in years 1..9999, and the oracle's answer must equal Python's.

| Operation | Cases | Coverage |
|---|---|---|
| `is_valid` | 4,619,538 | exhaustive: every `(y, m, d)` with `m` in 0..13 and `d` in 0..32 |
| `leap`, `dim` | 9,999 and 119,988 | exhaustive: every year, every month |
| `add_days(±1)` | 7,304,118 | exhaustive: every valid date, both directions |
| `lt` | 10,956,157 | exhaustive: every date against the next day (both orders) and itself |
| `add_months` | 10,437,744 | every (year, month) on days 1, 15 and 28..31, with 16 month steps up to ±100 years |
| `add_period`, structured | 708,240 | sampled: 26 special years (centuries, 400-year multiples, leap years, range edges), every month, days 1, 15, 28 and last, a grid of 640 periods |
| `add_period`, random | 295,514 | sampled: components up to ±500 years, ±6000 months, ±200,000 days |
| `add_days`, random | 200,000 | sampled: offsets around month, year and century lengths, some up to the full range |
| `lt`, random | 350,000 | sampled pairs |

The sampled rows add up to 1,553,754 cases. Two limits come from Python's range:

* When the true result leaves years 1..9999, Python has no answer. The test then only requires the oracle's result to be outside that range too; its value is not checked. This affects under 1% of the `add_period` cases and about 2% of the random `add_days` cases.
* `relativedelta` adds years and months first. Cases where that midpoint leaves the range are skipped (the spec has no range and could still end inside it): 78,960 of the 787,200 structured and 4,486 of the 300,000 random `add_period` cases, already excluded from the counts above.

### Against `java.time`: random samples in three year ranges

The oracle's answer must equal `java.time`'s as well. 
Each case starts from a random date in one of three ranges: inside Python's range, below it, and above it. 

| Operation | Years 1..9999 | Years −50,000..0 | Years 10,000..50,000 | Coverage |
|---|---|---|---|---|
| `is_valid` | 471,702 | 467,082 | 465,234 | every `(y, m, d)` grid triple for 1,000 random years plus special years (leap, century, 400-year, range edges, year 0) |
| `lt` | 200,000 | 200,000 | 200,000 | random pairs, a quarter of them in the same year or the same month |
| `add_days` | 200,000 | 200,000 | 200,000 | offsets around month, year and century lengths, some up to ±3,652,058 days |
| `add_months` | 100,000 | 100,000 | 100,000 | the 16 month steps, some random up to ±6000 months |
| `add_period` | 200,000 | 200,000 | 200,000 | components up to ±500 years, ±6000 months, ±200,000 days |
| **Total** | 1,171,702 | 1,167,082 | 1,165,234 | 3,504,018 cases |

Everything here is sampled; nothing is exhaustive. 
Nothing is checked for start dates outside years −50,000..50,000.

**Result:** the reference semantics agrees with both libraries on every case (56 tests, about 2 minutes on 6 workers).

What this shows: the reference semantics is the proleptic Gregorian calendar, and `add_period` follows the add-years-and-months, clamp-to-end-of-month, then add-days convention of `relativedelta` and `java.time`. 

## The trust chain, with this directory

```
reference semantics ≈ calendar        datetime (1..9999, exhaustive/structured/random),
                                      java.time (−50,000..50,000, random)                 (here)
encodings ≡ reference semantics       Verus                                               (proofs/)
implementation                        unit and property-based tests                       (tests/unit_tests/, tests/property_tests/)
models returned on DateSATBench       date operations evaluated by the Verus oracle       (DateSATBench/analysis/run/validation.py)
```

What remains trusted: Verus, Z3, the oracle's line driver, `datetime`/`relativedelta` and `java.time` (as oracles of the calendar). 
