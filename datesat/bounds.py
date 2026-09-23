"""
Date-bound configuration for the DateSAT bound-ablation study.

Three bound modes are supported, selected by name:

- "paper":    [1900-03-01 .. 2100-02-28] — the window used in the original
              (bounded) evaluation. Enforced symbolically on every DateVar
              (including intermediates) and concretely on Date/Period
              construction, reproducing the pre-unbounded semantics where an
              out-of-window intermediate makes the constraint UNSAT.
- "datetime": [0001-01-01 .. 9999-12-31] — Python's datetime.date representable
              range. Wide enough to be effectively unbounded for realistic
              constraints, while every model remains extractable and concretely
              validatable via datetime.
- "none":     no range bound at all (CURRENT DEFAULT). Only calendar
              well-formedness is asserted (month in [1,12], day valid for the
              month). Models may fall outside datetime's range, in which case
              concrete extraction / validation is best-effort.

Each mode is described by a BoundSpec giving the window in every native
representation the encodings use, so each encoding can assert it directly on
its own variables (epoch interval for epoch-days, alpha interval for
alpha-beta, Y/M/D bounds for simple/hybrid-YMD).

NOTE: BoundSpec assumes the window is month-aligned (starts on day 1 of a
month and ends on the last day of a month), which lets alpha-beta express it
as a pure alpha interval. Both presets satisfy this.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BoundSpec:
    """A date window expressed in every representation the encodings use."""

    name: str
    min_ymd: tuple  # (year, month, day) inclusive lower bound
    max_ymd: tuple  # (year, month, day) inclusive upper bound
    min_epoch: int  # days since 2000-03-01, inclusive
    max_epoch: int
    min_alpha: int  # months since 2000-03, inclusive
    max_alpha: int


# Original paper window [1900-03-01 .. 2100-02-28].
# Epoch days (epoch 2000-03-01): 1900-03-01 -> -36525, 2100-02-28 -> 36523.
# Alpha (months since 2000-03):  1900-03 -> -1200,     2100-02 -> 1199.
PAPER_BOUNDS = BoundSpec(
    name="paper",
    min_ymd=(1900, 3, 1),
    max_ymd=(2100, 2, 28),
    min_epoch=-36525,
    max_epoch=36523,
    min_alpha=-1200,
    max_alpha=1199,
)

# Python datetime.date representable range [0001-01-01 .. 9999-12-31].
# Epoch days: 0001-01-01 -> -730179, 9999-12-31 -> 2921879.
# Alpha:      0001-01    -> -23990,  9999-12    -> 95997.
DATETIME_BOUNDS = BoundSpec(
    name="datetime",
    min_ymd=(1, 1, 1),
    max_ymd=(9999, 12, 31),
    min_epoch=-730179,
    max_epoch=2921879,
    min_alpha=-23990,
    max_alpha=95997,
)

BOUND_MODES = {
    "paper": PAPER_BOUNDS,
    "datetime": DATETIME_BOUNDS,
    "none": None,
}

# Default is now unbounded (no range constraints on symbolic variables).
DEFAULT_BOUND_MODE = "none"


def get_bound_spec(mode: str) -> Optional[BoundSpec]:
    """Resolve a bound mode name to its BoundSpec (None for mode 'none')."""
    if mode not in BOUND_MODES:
        raise ValueError(
            f"Unknown bound mode: {mode!r}. Must be one of {sorted(BOUND_MODES)}"
        )
    return BOUND_MODES[mode]
