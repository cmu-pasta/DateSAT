use vstd::prelude::*;

verus! {

    /// A calendar period expressed as (years, months, days).
    pub struct Period(pub int, pub int, pub int);

    impl Period {
        pub open spec fn years(&self) -> int {
            self.0
        }

        pub open spec fn months(&self) -> int {
            self.1
        }
        pub open spec fn days(&self) -> int {
            self.2
        }

        /// Component-wise addition of two periods.
        spec fn add(self, other: Self) -> Period {
            Period(self.years() + other.years(),
                self.months() + other.months(), self.days() + other.days())
        }

        /// Component-wise scaling of a period by an integer factor.
        spec fn scale(self, factor: int) -> Period {
            Period(self.years() * factor, self.months() * factor, self.days() * factor)
        }
    }

    proof fn lemma_period_add_zero_identity(p: Period)
        ensures p.add(Period(0,0,0)) == p {}

    proof fn lemma_period_add_commutative(p1: Period, p2: Period)
        ensures p1.add(p2) == p2.add(p1) {}

    proof fn lemma_period_add_associative(p1: Period, p2: Period, p3: Period)
        ensures p1.add(p2).add(p3) == p1.add(p2.add(p3)) {}

    proof fn lemma_period_scale_identity(p: Period)
        ensures p.scale(1) == p {}

    #[cfg(slow_proofs)]
    proof fn lemma_period_scale_commutative(p: Period, f1: int, f2: int) by (nonlinear_arith)
        ensures p.scale(f1).scale(f2) == p.scale(f2).scale(f1) {}

    #[cfg(slow_proofs)]
    proof fn lemma_period_scale_associative(p: Period, f1: int, f2: int) by (nonlinear_arith)
        ensures p.scale(f1).scale(f2) == p.scale(f1*f2) {}

} // verus!
