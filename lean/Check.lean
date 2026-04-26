import DateSATSemantics
import DateSATNaive

/-
DateSATNaiveEquiv.lean

This file is the bridge between:

* `DateSATSemantics.lean`  -- the paper-style relational semantics
* `DateSATNaive.lean`      -- the executable Option A model of the Naive encoding

The main idea is simple:

  the semantic file says what date-period addition means,
  the naive file computes a result in an implementation-style way,
  and the theorems here state that those two views coincide.

Because the current environment does not have Lean installed, the proofs are
left as `sorry` blocks. The file is still structured so you can run it in Lean,
see the goal states, and discharge the proofs incrementally.
-/

namespace DateSAT

/-! ## Local helper: semantic determinism target

The semantic file presents `+P` as a normalization relation. The theorem below
states the exact result that the executable naive model is expected to realize.
-/

def naiveSemanticResult (d : Date) (p : Period) : RawDate :=
  (naiveAddPeriod d p).1

/-! ## Step-by-step correspondence lemmas -/

/-- The executable month-add phase realizes the paper's `Add-Months` rule. -/
theorem naive_addMonths_matches_semantics
    (d : RawDate) (n : Int)
    (hvalid : Valid d) :
    Step (Expr.addM (Expr.val d) n)
         (Expr.val (naiveAddMonths d n)) := by
  unfold naiveAddMonths
  refine Step.addMonths
    (d := d)
    (n := n)
    (y' := d.year + DateSAT.floorDiv (d.month - 1 + n) 12)
    (m' := 1 + DateSAT.floorMod (d.month - 1 + n) 12)
    hvalid
    ?_
    ?_
  · rfl
  · rfl

/-- One forward/backward day-step iteration computes a semantic normalization. -/
theorem naive_addDays_matches_semantics
    (d : RawDate) (n : Int)
    (hvalid : Valid d) :
    NormalizesTo (Expr.addD (Expr.val d) n)
                 (naiveAddDays d n) := by
  sorry

/-- The full executable naive model is sound with respect to the paper semantics. -/
theorem naive_addPeriod_sound
    (d : Date) (p : Period) :
    AddPeriodNormalizes d.1 p (naiveSemanticResult d p) := by
  sorry

/-! ## Uniqueness / exact equality target

The next theorem is the one that really captures "they are the same": if the
relational semantics normalizes to some `d'`, then that `d'` must be exactly the
raw date computed by the executable naive model.

This theorem will usually depend on a normalization-uniqueness fact proved in
`DateSATSemantics.lean`.
-/

theorem naive_addPeriod_complete
    (d : Date) (p : Period) (d' : RawDate) :
    AddPeriodNormalizes d.1 p d' → d' = naiveSemanticResult d p := by
  sorry

/-- Final equivalence statement: semantic normalization iff equality to naive result. -/
theorem naive_addPeriod_equiv
    (d : Date) (p : Period) (d' : RawDate) :
    AddPeriodNormalizes d.1 p d' ↔ d' = naiveSemanticResult d p := by
  constructor
  · intro h
    exact naive_addPeriod_complete d p d' h
  · intro h
    simpa [naiveSemanticResult, h] using naive_addPeriod_sound d p

/-! ## Smoke tests

These do not prove anything. They just let you run the executable naive model
on a few representative examples from the paper's date arithmetic behavior.
-/

#eval naiveAddPeriodRaw (mkRawDate 2024 1 31) { years := 0, months := 1, days := 0 }
#eval naiveAddPeriodRaw (mkRawDate 2023 1 31) { years := 0, months := 1, days := 0 }
#eval naiveAddPeriodRaw (mkRawDate 2024 3 1)  { years := 0, months := 0, days := -1 }
#eval naiveAddPeriodRaw (mkRawDate 2024 1 30) { years := 1, months := 2, days := 15 }

end DateSAT
