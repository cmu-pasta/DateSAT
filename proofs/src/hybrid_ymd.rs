use vstd::prelude::*;
use crate::*;

verus! {

    /// A hybrid date representation that can hold a YMD form, an epoch-delta form, or both.
    ///
    /// Fields: (year, month, day, delta, ymd, epoch)
    ///   - If `ymd`   is true, SimpleDate(year, month, day) is a valid representation of this date.
    ///   - If `epoch` is true, EpochDelta(delta) is a valid representation of this date.
    ///   - At least one flag must always be true.
    ///   - Both may be true when the two representations are consistent.
    pub struct Hybrid(pub int, pub int, pub int, pub int, pub bool, pub bool);

    impl Hybrid {
        pub open spec fn _year(&self) -> int { self.0 }
        pub open spec fn _month(&self) -> int { self.1 }
        pub open spec fn _day(&self) -> int { self.2 }
        pub open spec fn delta(&self) -> int { self.3 }
        pub open spec fn ymd(&self) -> bool { self.4 }
        pub open spec fn epoch(&self) -> bool { self.5 }

        /// A Hybrid is valid when:
        ///   - at least one representation flag is set, and
        ///   - if the YMD flag is set, the stored (year, month, day) form a valid date.
        /// (Consistency between the two representations is a separate concern.)
        pub open spec fn is_valid(self) -> bool {
            (self.ymd() || self.epoch())
            && (self.ymd() ==> SimpleDate(self._year(), self._month(), self._day()).is_valid())
        }

        /// Construct a Hybrid from a YMD date (lazy: epoch delta is not computed).
        pub open spec fn from_simple_date(date: SimpleDate) -> Hybrid {
            Hybrid(date.year(), date.month(), date.day(), 0, true, false)
        }

        /// Construct a Hybrid from an EpochDelta (lazy: YMD components are not computed).
        pub open spec fn from_epoch_delta(ed: EpochDelta) -> Hybrid {
            Hybrid(0, 0, 0, ed.delta(), false, true)
        }

        /// Recover the YMD date.
        /// Uses the stored YMD components directly when available, otherwise converts
        /// from the epoch delta.
        pub open spec fn to_ymd(self) -> SimpleDate {
            if self.ymd() {
                SimpleDate(self._year(), self._month(), self._day())
            } else {
                EpochDelta(self.delta()).to_ymd()
            }
        }

        /// Recover the EpochDelta.
        /// Uses the stored delta directly when available (preferred), otherwise converts
        /// from the YMD components.
        pub open spec fn to_epoch_delta(self) -> EpochDelta {
            if self.epoch() {
                EpochDelta(self.delta())
            } else {
                EpochDelta::from_simple_date(SimpleDate(self._year(), self._month(), self._day()))
            }
        }

        /// Less-than comparison.
        /// Prefers epoch delta form (integer comparison) when both have `epoch` set;
        /// falls back to SimpleDate::lt when both have `ymd` set;
        /// converts to epoch delta when flags are inconsistent.
        pub open spec fn lt(self, other: Self) -> bool {
            if self.epoch() && other.epoch() {
                self.to_epoch_delta().lt(other.to_epoch_delta()) // fast
            } else if self.ymd() && other.ymd() {
                self.to_ymd().lt(other.to_ymd())// fast
            } else {
                self.to_epoch_delta().lt(other.to_epoch_delta()) // slow
            }
        }

        /// Equality comparison (not structural — respects lazy semantics).
        /// Same flag-priority logic as lt.
        pub open spec fn eq(self, other: Self) -> bool {
            if self.epoch() && other.epoch() {
                self.to_epoch_delta() == other.to_epoch_delta() // fast
            } else if self.ymd() && other.ymd() {
                self.to_ymd() == other.to_ymd() // fast
            } else {
                self.to_epoch_delta() == other.to_epoch_delta() // slow
            }
        }

        /// Less-than-or-equal, defined as lt or eq.
        pub open spec fn leq(self, other: Self) -> bool {
            self.lt(other) || self.eq(other)
        }

        /// Add a period to this hybrid date, choosing the most efficient representation.
        ///
        /// Case 1 — pure day addition (years == 0, months == 0):
        ///   Use epoch delta semantics (just integer addition). Result is epoch-only.
        ///
        /// Case 2 — year/month addition with no day component (days == 0):
        ///   Use YMD semantics (add_months). Result is YMD-only.
        ///
        /// Case 3 — year/month addition with a non-zero day component:
        ///   Add years/months in YMD, then convert to epoch and add days by integer
        ///   arithmetic (avoiding the recursive SimpleDate::add_days entirely). Result is epoch-only.
        pub open spec fn add_period(self, p: Period) -> Hybrid {
            if p.years() == 0 && p.months() == 0 {
                // Case 1: pure day addition — epoch arithmetic
                Hybrid(0, 0, 0, self.to_epoch_delta().delta() + p.days(), false, true)
            } else if p.days() == 0 {
                // Case 2: year/month addition only — stay in YMD form
                let d = self.to_ymd().add_months(p.years() * 12 + p.months());
                Hybrid(d.year(), d.month(), d.day(), 0, true, false)
            } else {
                // Case 3: year/month + day — add months in YMD, convert to epoch, add days
                let d = self.to_ymd().add_months(p.years() * 12 + p.months());
                let ed = EpochDelta::from_simple_date(d);
                Hybrid(0, 0, 0, ed.delta() + p.days(), false, true)
            }
        }
    }

    impl DateEncoding for Hybrid {
        open spec fn from_ymd(y: int, m: int, d: int) -> Hybrid {
            Hybrid::from_simple_date(SimpleDate(y, m, d))
        }

        open spec fn year(self) -> int {
            if self.ymd() { self._year() } else { self.to_ymd().year() }
        }

        open spec fn month(self) -> int {
            if self.ymd() { self._month() } else { self.to_ymd().month() }
        }

        open spec fn day(self) -> int {
            if self.ymd() { self._day() } else { self.to_ymd().day() }
        }

        open spec fn lt(self, other: Self) -> bool {
            self.lt(other)
        }

        open spec fn eq(self, other: Self) -> bool {
            self.eq(other)
        }

        open spec fn add_period(self, period: Period) -> Hybrid {
            self.add_period(period)
        }
    }

    /// Congruence between a SimpleDate and a Hybrid, respecting the lazy representation.
    /// In order to be congruent, the Hybrid representation must be valid. Then:
    /// If `ymd` is set, the stored YMD must match the date.
    /// If `epoch` is set, the stored delta must equal from_ymd(d).
    pub open spec fn hybrid_congruent(d: SimpleDate, h: Hybrid) -> bool {
        h.is_valid() &&
        (h.ymd() ==> d == SimpleDate(h.year(), h.month(), h.day()))
        && (h.epoch() ==> EpochDelta(h.delta()) == EpochDelta::from_ymd(d.year(), d.month(), d.day()))
    }

    // ── Hybrid congruence proofs ──────────────────────────────────────

    // Hybrid congruence at construction: from_ymd produces a congruent Hybrid.
    pub proof fn theorem_hybrid_from_ymd_congruent(y: int, m: int, d: int)
        requires SimpleDate(y, m, d).is_valid(),
        ensures hybrid_congruent(SimpleDate(y, m, d), Hybrid::from_ymd(y, m, d)),
    {}

    // Hybrid congruence at construction: from_epoch_delta produces a congruent Hybrid.
    pub proof fn theorem_hybrid_from_epoch_delta_congruent(ed: EpochDelta)
        ensures hybrid_congruent(ed.to_ymd(), Hybrid::from_epoch_delta(ed)),
    {
        theorem_epoch_delta_from_simple_date_to_ymd_inverse(ed);
    }

    // Hybrid::to_ymd recovers the congruent SimpleDate.
    pub proof fn lemma_hybrid_to_ymd(d: SimpleDate, h: Hybrid)
        requires d.is_valid(), hybrid_congruent(d, h), h.ymd() || h.epoch(),
        ensures h.to_ymd() == d,
    {
        if h.ymd() {
            // Stored YMD matches d directly.
        } else {
            // epoch flag is set: EpochDelta(h.delta()) == from_simple_date(d)
            // h.to_ymd() = EpochDelta(h.delta()).to_ymd() = from_simple_date(d).to_ymd() = d
            theorem_epoch_delta_to_ymd_from_simple_date_inverse(d);
        }
    }

    // Hybrid::to_epoch_delta recovers the congruent EpochDelta.
    pub proof fn lemma_hybrid_to_epoch_delta(d: SimpleDate, h: Hybrid)
        requires d.is_valid(), hybrid_congruent(d, h), h.ymd() || h.epoch(),
        ensures h.to_epoch_delta() == EpochDelta::from_simple_date(d),
    {
        if h.epoch() {
            // Stored delta matches from_simple_date(d) directly.
        } else {
            // ymd flag is set: d == SimpleDate(h.year(), h.month(), h.day())
            // h.to_epoch_delta() = from_simple_date(SimpleDate(h.year(), h.month(), h.day())) = from_simple_date(d)
        }
    }

    // Hybrid congruent pairs preserve comparison.
    pub proof fn theorem_hybrid_congruent_preserves_comparison(
        d1: SimpleDate, h1: Hybrid, d2: SimpleDate, h2: Hybrid,
    )
        requires
            d1.is_valid(), d2.is_valid(),
            hybrid_congruent(d1, h1), hybrid_congruent(d2, h2),
            h1.ymd() || h1.epoch(), h2.ymd() || h2.epoch(),
        ensures
            (h1.lt(h2) <==> d1.lt(d2)),
            (h1.eq(h2) <==> d1.eq(d2)),
    {
        // Establish that accessors recover the right values.
        lemma_hybrid_to_ymd(d1, h1);
        lemma_hybrid_to_ymd(d2, h2);
        lemma_hybrid_to_epoch_delta(d1, h1);
        lemma_hybrid_to_epoch_delta(d2, h2);

        // Now h1.to_ymd() == d1, h2.to_ymd() == d2,
        //     h1.to_epoch_delta() == from_simple_date(d1), h2.to_epoch_delta() == from_simple_date(d2).

        // For the epoch-delta branches, we need the EpochDelta congruence theorem.
        let ed1 = EpochDelta::from_simple_date(d1);
        let ed2 = EpochDelta::from_simple_date(d2);
        theorem_epoch_delta_congruent_preserves_comparison(d1, ed1, d2, ed2);

        // All three branches of Hybrid::lt and Hybrid::eq now reduce to
        // either SimpleDate or EpochDelta comparison, both of which agree with d1.lt(d2) / d1 == d2.
    }

    // Hybrid congruence is preserved under period addition.
    pub proof fn theorem_hybrid_add_period_preserves_congruence(d: SimpleDate, h: Hybrid, p: Period)
        requires d.is_valid(), hybrid_congruent(d, h),
        ensures hybrid_congruent(d.add_period(p), h.add_period(p))
    {
        let n = p.years() * 12 + p.months();
        let days = p.days();

        // Recover accessors.
        lemma_hybrid_to_ymd(d, h);
        lemma_hybrid_to_epoch_delta(d, h);
        // Now: h.to_ymd() == d, h.to_epoch_delta() == from_simple_date(d).

        if p.years() == 0 && p.months() == 0 {
            // Case 1: pure day addition.
            // h.add_period(p) = Hybrid(0,0,0, h.to_epoch_delta().delta() + days, false, true)
            // Need: EpochDelta(from_simple_date(d).delta() + days) == from_simple_date(d.add_period(p))
            // d.add_period(p) = d.add_months(0).add_days(days) = d.add_days(days)
            lemma_from_simple_date_add_days(d, days);
        } else if p.days() == 0 {
            // Case 2: year/month only.
            // h.add_period(p) = Hybrid(d'.year(), d'.month(), d'.day(), 0, true, false)
            //   where d' = h.to_ymd().add_months(n) = d.add_months(n)
            // d.add_period(p) = d.add_months(n).add_days(0) = d.add_months(n)
            // Need: d.add_period(p) == d.add_months(n), which holds since add_days(0) is identity.
            // The YMD flag is set and matches, so hybrid_congruent holds.
        } else {
            // Case 3: mixed year/month + days.
            // h.add_period(p) = Hybrid(0,0,0, from_simple_date(d.add_months(n)).delta() + days, false, true)
            // d.add_period(p) = d.add_months(n).add_days(days)
            // Need: EpochDelta(from_simple_date(d.add_months(n)).delta() + days) == from_simple_date(d.add_months(n).add_days(days))
            lemma_date_add_months_preserves_validity(d, n);
            lemma_from_simple_date_add_days(d.add_months(n), days);
        }
    }

} // verus!
