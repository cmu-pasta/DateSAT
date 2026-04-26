import DateSATSemantics

/-
DateSATNaive.lean

An implementation-style model of the Naive encoding on concrete Date.

This file does NOT build SMT constraints. Instead, it gives an executable Lean
function that follows the same algorithmic shape as the paper's Naive encoding:

  1. represent a date explicitly as a (year, month, day) triple,
  2. normalize year/month using floor division/modulo,
  3. clamp the day to the end of the target month,
  4. carry days forward/backward one day at a time.

It is meant to be proved equivalent to the semantic relation in
DateSATSemantics.lean.
-/

namespace DateSAT

/-! ## Naive month normalization -/

/--
The month-add phase from the paper's Naive encoding:

* compute the target year/month with floor division/modulo,
* then clamp the day using `min day (dim y' m')`.
-/
def naiveAddMonths (d : RawDate) (n : Int) : RawDate :=
  let k  := d.month - 1 + n
  let y' := d.year + floorDiv k 12
  let m' := 1 + floorMod k 12
  let d' := min d.day (dim y' m')
  mkRawDate y' m' d'

/-! ## One-day stepping -/

/--
Advance by one day.

Intended to mirror the `Add-Days` / `Add-Days-Over` behavior from Figure 3,
but in executable form.
-/
def naiveNextDay (d : RawDate) : RawDate :=
  if d.day < dim d.year d.month then
    mkRawDate d.year d.month (d.day + 1)
  else
    let d1 := withDay d 1
    let d2 := naiveAddMonths d1 1
    mkRawDate d2.year d2.month 1

/--
Go back by one day.

Intended to mirror the `Add-Days-Under1` / `Add-Days-Under2` behavior from
Figure 3, but in executable form.
-/
def naivePrevDay (d : RawDate) : RawDate :=
  if 1 < d.day then
    mkRawDate d.year d.month (d.day - 1)
  else
    let d1 := withDay d 1
    let d2 := naiveAddMonths d1 (-1)
    mkRawDate d2.year d2.month (dim d2.year d2.month)

/-! ## Iterated day addition -/

def naiveAddDaysPos : RawDate → Nat → RawDate
  | d, 0       => d
  | d, n + 1   => naiveAddDaysPos (naiveNextDay d) n


def naiveAddDaysNeg : RawDate → Nat → RawDate
  | d, 0       => d
  | d, n + 1   => naiveAddDaysNeg (naivePrevDay d) n

/-- Add an arbitrary integer number of days by repeated one-day stepping. -/
def naiveAddDays (d : RawDate) (n : Int) : RawDate :=
  if h : 0 ≤ n then
    naiveAddDaysPos d n.toNat
  else
    naiveAddDaysNeg d (-n).toNat

/-! ## Full naive add-period -/

/--
The paper's Naive encoding is structured as:

1. add years/months together as a single month offset,
2. perform the month normalization + clamp step,
3. then carry the day offset one step at a time.
-/
def naiveAddPeriodRaw (d : RawDate) (p : Period) : RawDate :=
  let totalMonths := 12 * p.years + p.months
  let d' := naiveAddMonths d totalMonths
  naiveAddDays d' p.days

/-! ## Expected proof obligations

These are the preservation lemmas you will want later so that the executable
Naive model returns actual semantic dates when started from the semantic domain.
-/

theorem naiveAddMonths_preserves_valid
    {d : RawDate} {n : Int}
    (h : Valid d) :
    Valid (naiveAddMonths d n) := by
  sorry


theorem naiveNextDay_preserves_valid
    {d : RawDate}
    (h : Valid d) :
    Valid (naiveNextDay d) := by
  sorry


theorem naivePrevDay_preserves_valid
    {d : RawDate}
    (h : Valid d) :
    Valid (naivePrevDay d) := by
  sorry


theorem naiveAddDays_preserves_valid
    {d : RawDate} {n : Int}
    (h : Valid d) :
    Valid (naiveAddDays d n) := by
  sorry


theorem naiveAddPeriodRaw_preserves_valid
    {d : RawDate} {p : Period}
    (h : Valid d) :
    Valid (naiveAddPeriodRaw d p) := by
  sorry

/--
A safe wrapper over the paper's semantic domain `Date`.

This is the executable counterpart of applying the Naive encoding to a valid
source date.
-/
def naiveAddPeriod (d : Date) (p : Period) : Date :=
  ⟨naiveAddPeriodRaw d.1 p, naiveAddPeriodRaw_preserves_valid d.2⟩

/-! ## Derived comparison operators in the same executable style -/

def naiveDateLe (d1 d2 : RawDate) : Prop :=
  d1.year < d2.year ∨
  (d1.year = d2.year ∧ d1.month < d2.month) ∨
  (d1.year = d2.year ∧ d1.month = d2.month ∧ d1.day ≤ d2.day)


def naiveDateLt (d1 d2 : RawDate) : Prop :=
  naiveDateLe d1 d2 ∧ ¬ naiveDateLe d2 d1

/-- Same comparison, but on the semantic domain `Date`. -/
def naiveDateLtOnDomain (d1 d2 : Date) : Prop :=
  naiveDateLt d1.1 d2.1

end DateSAT
