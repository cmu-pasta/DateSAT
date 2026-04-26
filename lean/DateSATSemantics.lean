/-
DateSATSemantics.lean

A Lean 4 formalization of the semantics from Section 3.1 and Figure 3 of the
DateSAT paper.

This file is intentionally the semantic layer, not an encoding into arithmetic.
It mirrors the paper's objects directly:
  * dates as Gregorian-valid triples,
  * periods as integer triples,
  * lexicographic date comparison,
  * the small-step rules for +M, +D, and +P,
  * normalization as the reflexive-transitive closure of the small-step rules.
-/

namespace DateSAT

/-! ## Basic domains -/

structure RawDate where
  year  : Int
  month : Int
  day   : Int
  deriving Repr, DecidableEq

structure Period where
  years  : Int
  months : Int
  days   : Int
  deriving Repr, DecidableEq

/-- Gregorian leap-year rule. -/
def isLeap (y : Int) : Prop :=
  y % 4 = 0 ∧ (y % 100 ≠ 0 ∨ y % 400 = 0)

instance (y : Int) : Decidable (isLeap y) := by
  unfold isLeap
  infer_instance

/--
Days in month.

The paper only needs `dim(y,m)` on calendar months `m ∈ {1, ..., 12}`.
For out-of-range months we return `0`; semantic rules are only meant to be used
from valid dates, so this branch is outside the intended semantic domain.
-/
def dim (y m : Int) : Int :=
  if m = 1 ∨ m = 3 ∨ m = 5 ∨ m = 7 ∨ m = 8 ∨ m = 10 ∨ m = 12 then 31
  else if m = 4 ∨ m = 6 ∨ m = 9 ∨ m = 11 then 30
  else if m = 2 then (if isLeap y then 29 else 28)
  else 0

/-- Definition 1 from the paper. -/
def Valid (d : RawDate) : Prop :=
  1 ≤ d.month ∧ d.month ≤ 12 ∧ 1 ≤ d.day ∧ d.day ≤ dim d.year d.month

/-- The paper's semantic domain `D` of valid dates. -/
abbrev Date := { d : RawDate // Valid d }

/-- Convenience constructor for raw triples. -/
def mkRawDate (y m d : Int) : RawDate :=
  { year := y, month := m, day := d }

/-- Replace only the day field. -/
def withDay (d : RawDate) (newDay : Int) : RawDate :=
  { d with day := newDay }

/-! ## Date comparison -/

/-- Definition 2 from the paper: lexicographic `≤` on dates. -/
def dateLe (d1 d2 : RawDate) : Prop :=
  d1.year < d2.year ∨
  (d1.year = d2.year ∧ d1.month < d2.month) ∨
  (d1.year = d2.year ∧ d1.month = d2.month ∧ d1.day ≤ d2.day)

/-- Strict lexicographic `<`, derived from `≤`. -/
def dateLt (d1 d2 : RawDate) : Prop :=
  dateLe d1 d2 ∧ ¬ dateLe d2 d1

/-! ## Period operations from Definition 3 -/

/-- Element-wise addition of periods. -/
def periodAdd (p1 p2 : Period) : Period :=
  { years := p1.years + p2.years
  , months := p1.months + p2.months
  , days := p1.days + p2.days }

/-- Scaling a period by an integral constant. -/
def periodScale (k : Int) (p : Period) : Period :=
  { years := k * p.years
  , months := k * p.months
  , days := k * p.days }

/-! ## Arithmetic expressions for the small-step semantics -/

/--
This syntax mirrors the shapes that appear in Figure 3.
A term is either already a date value, or a pending `+m`, `+D`, or `+P`.
-/
inductive Expr where
  | val  : RawDate → Expr
  | addM : Expr → Int → Expr
  | addD : Expr → Int → Expr
  | addP : Expr → Period → Expr
  deriving Repr, DecidableEq

open Expr

/-! ## Floor division / modulo used by Add-Months

The paper's Add-Months rule uses Euclidean / floor-style division by `12`.
Lean's `/` on `Int` is not the same thing for negative values, so we define the
intended operations explicitly.
-/

def floorDiv (a b : Int) : Int :=
  let q := a / b
  let r := a % b
  if r ≠ 0 ∧ ((r < 0) ≠ (b < 0)) then q - 1 else q

def floorMod (a b : Int) : Int :=
  a - floorDiv a b * b

/-! ## Figure 3 small-step semantics -/

/--
`Step e e'` means expression `e` takes one semantic small-step to `e'`.
This is the paper's Figure 3, rendered directly into Lean.
-/
inductive Step : Expr → Expr → Prop where
  /-- Add-Months -/
  | addMonths
      (d : RawDate) (n y' m' : Int)
      (hvalid : Valid d)
      (hy : y' = d.year + floorDiv (d.month - 1 + n) 12)
      (hm : m' = 1 + floorMod (d.month - 1 + n) 12) :
      Step (addM (val d) n)
           (val (mkRawDate y' m' (min d.day (dim y' m'))))

  /-- Add-Days -/
  | addDays
      (d : RawDate) (n : Int)
      (hvalid : Valid d)
      (hlo : 1 ≤ d.day + n)
      (hhi : d.day + n ≤ dim d.year d.month) :
      Step (addD (val d) n)
           (val (mkRawDate d.year d.month (d.day + n)))

  /-- Add-Days-Over -/
  | addDaysOver
      (d : RawDate) (n : Int)
      (hvalid : Valid d)
      (hover : d.day + n > dim d.year d.month) :
      Step (addD (val d) n)
           (addD (addM (val (withDay d 1)) 1)
                 (n - (dim d.year d.month - d.day) - 1))

  /-- Add-Days-Under1 -/
  | addDaysUnder1
      (d : RawDate) (n : Int)
      (hvalid : Valid d)
      (hday : 1 < d.day)
      (hunder : d.day + n ≤ 0) :
      Step (addD (val d) n)
           (addD (val (withDay d 1)) (d.day - 1 + n))

  /-- Add-Days-Under2 -/
  | addDaysUnder2
      (d d' : RawDate) (n : Int)
      (hvalid : Valid d)
      (hunder : 1 + n ≤ 0)
      (hprev : Step (addM (val (withDay d 1)) (-1)) (val d')) :
      Step (addD (val d) n)
           (addD (val d') (n + dim d'.year d'.month))

  /-- Add-Comp where `+δ` is `+m`. -/
  | addCompM
      {e e' : Expr} (n : Int)
      (h : Step e e') :
      Step (addM e n) (addM e' n)

  /-- Add-Comp where `+δ` is `+D`. -/
  | addCompD
      {e e' : Expr} (n : Int)
      (h : Step e e') :
      Step (addD e n) (addD e' n)

  /-- Add-Period -/
  | addPeriod
      (d : RawDate) (p : Period)
      (hvalid : Valid d) :
      Step (addP (val d) p)
           (addD (addM (val d) (12 * p.years + p.months)) p.days)

/-! ## Reflexive-transitive closure (normalization) -/

inductive Star {α : Type} (R : α → α → Prop) : α → α → Prop where
  | refl (a : α) : Star R a a
  | tail {a b c : α} : R a b → Star R b c → Star R a c

/-- `e` normalizes to the date `d`. -/
def NormalizesTo (e : Expr) (d : RawDate) : Prop :=
  Star Step e (Expr.val d)

/-- The paper's normalized date-period addition relation `D +P P *→ D'`. -/
def AddPeriodNormalizes (d : RawDate) (p : Period) (d' : RawDate) : Prop :=
  NormalizesTo (Expr.addP (Expr.val d) p) d'

/--
A convenient derived notion that starts from an actually valid date in the paper's
semantic domain `D`.
-/
def AddPeriodOnDomain (d : Date) (p : Period) (d' : Date) : Prop :=
  AddPeriodNormalizes d.1 p d'.1

/-! ## Optional derived “abuse of notation” layer

The paper says that after Theorem 1, it abuses `+P` to mean the unique
normalized result. We do not define that function here, because doing so cleanly
really belongs after proving normalization + uniqueness.

At this stage, the semantic content is the relation `AddPeriodNormalizes`.
-/

/--
A direct statement of Theorem 1's shape, left as a theorem to prove later.
-/
theorem normalization_and_well_formedness_statement :
    ∀ (d : Date) (p : Period),
      ∃ d' : RawDate, Valid d' ∧ AddPeriodNormalizes d.1 p d' := by
  sorry

end DateSAT
