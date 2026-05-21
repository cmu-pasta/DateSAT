use vstd::prelude::*;
use crate::*;

verus! {

    /// A date represented as the number of days since the EPOCH (2000-03-01).
    pub struct EpochDelta(pub int);

    impl EpochDelta {
        pub open spec fn delta(&self) -> int {
            self.0
        }

        /// Strict ordering on epoch deltas: compares the underlying integer offsets.
        pub open spec fn lt(self, other: Self) -> bool {
            self.delta() < other.delta()
        }

        /// Equality: compares the underlying integer offsets.
        pub open spec fn eq(self, other: Self) -> bool {
            self.delta() == other.delta()
        }

        /// Non-strict ordering on epoch deltas: compares the underlying integer offsets.
        pub open spec fn leq(self, other: Self) -> bool {
            self.delta() <= other.delta()
        }

        /// Convert an epoch delta to a YMD date by adding delta days to the EPOCH.
        pub open spec fn to_ymd(self) -> SimpleDate
        {
            EPOCH.add_days(self.delta())
        }

        /// Convert a YMD date to an epoch delta using a closed-form formula.
        ///
        /// The formula counts days from EPOCH (2000-03-01) in three parts:
        ///   1. Days contributed by full years elapsed since the epoch.
        ///   2. Days contributed by full months elapsed since March.
        ///   3. Days elapsed within the current calendar month.
        pub open spec fn from_simple_date(date: SimpleDate) -> EpochDelta
            recommends EPOCH == SimpleDate(2000, 3, 1) // the logic depends on the specific value of EPOCH
        {
            // First count how many days elapsed owing to the years elapsed since Mar 1, 2000
            let ye = years_since_epoch(date.year(), date.month());
            let days_by_years = 365*ye + leap_correction(ye);

            // Then count how many days elapsed owing to the months elapsed since March
            let me = months_since_march(date.month());

            // Note: This is some wacky logic, but it works.
            // Since March, the dim array is [31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 28_or_29]
            // Cumulatively for months elapsed in the range 0..11 inclusive, this is
            //   [0, 31, 61, 92, 122, 153, 184, 214, 245, 275, 306, 337]
            // It turns out that this is basically (153 * X + 2) / 5, assuming floor division.
            let days_by_months = (153*me + 2)/5;

            // Then count how many days elapsed in the current calendar month
            let days_by_dim = date.day() - 1;

            // That's your epoch delta
            EpochDelta(days_by_years + days_by_months + days_by_dim)
        }

        /// Add n days to this epoch delta (simple integer addition).
        pub open spec fn add_days(self, n: int) -> EpochDelta {
            EpochDelta(self.delta() + n)
        }

        /// Add n months by converting to YMD, applying add_months, and converting back.
        pub open spec fn add_months(self, n: int) -> EpochDelta {
            EpochDelta::from_simple_date(self.to_ymd().add_months(n))
        }

        /// Add a calendar period: first add years/months, then add days.
        pub open spec fn add_period(self, period: Period) -> EpochDelta {
            self.add_months(period.years() * 12 + period.months()).add_days(period.days())
        }
    }

    impl DateEncoding for EpochDelta {
        open spec fn from_ymd(y: int, m: int, d: int) -> EpochDelta {
            EpochDelta::from_simple_date(SimpleDate(y, m, d))
        }

        open spec fn year(self) -> int {
            self.to_ymd().year()
        }

        open spec fn month(self) -> int {
            self.to_ymd().month()
        }

        open spec fn day(self) -> int {
            self.to_ymd().day()
        }

        open spec fn lt(self, other: Self) -> bool {
            self.lt(other)
        }

        open spec fn eq(self, other: Self) -> bool {
            self.eq(other)
        }

        open spec fn add_period(self, period: Period) -> EpochDelta {
            self.add_period(period)
        }
    }

    // ── Helper spec functions for the from_simple_date formula ─────────────────

    /// Years elapsed since the epoch (March 1, 2000).
    /// Months Jan-Feb are counted as part of the previous year,
    /// so that the leap day (Feb 29) falls at the end of the epoch-year.
    pub open spec fn years_since_epoch(y: int, m: int) -> int {
        (if m <= 2 { y - 1 } else { y }) - 2000
    }

    /// Months elapsed since March, where March = 0 .. February = 11.
    pub open spec fn months_since_march(m: int) -> int {
        if m <= 2 { m + 9 } else { m - 3 }
    }

    /// Leap-year correction for k years: number of leap years in [1..k] relative to 2000.
    /// Since 2000 = 0 (mod 400), this is simply k/4 - k/100 + k/400.
    pub open spec fn leap_correction(k: int) -> int {
        k/4 - k/100 + k/400
    }

    // ── EpochDelta congruence proofs ───────────────────────────────────

    // The EPOCH is at delta = 0
    pub proof fn lemma_epoch_is_at_delta_zero() ensures
        EpochDelta::from_simple_date(EPOCH).delta() == 0 {}

    // A date with delta = 0 is the EPOCH
    pub proof fn lemma_delta_zero_is_epoch() ensures
        EpochDelta::to_ymd(EpochDelta(0)) == EPOCH {}

    /// Congruence between SimpleDate and EpochDelta: asserts they are related by from_ymd.
    /// Whether this relation preserves comparison and arithmetic is proven below.
    pub open spec fn ed_congruent(d: SimpleDate, ed: EpochDelta) -> bool {
        ed == EpochDelta::from_ymd(d.year(), d.month(), d.day())
    }

    // Congruence at construction: from_ymd is congruent with SimpleDate.
    pub proof fn theorem_epoch_delta_from_ymd_congruent(y: int, m: int, d: int)
        ensures ed_congruent(SimpleDate(y, m, d), EpochDelta::from_ymd(y, m, d)),
    {}

    // The from_simple_date delta for any date = first-of-month value + (day - 1)
    proof fn lemma_from_simple_date_day_offset(y: int, m: int, d: int)
        ensures EpochDelta::from_simple_date(SimpleDate(y, m, d)).delta()
        == EpochDelta::from_simple_date(SimpleDate(y, m, 1)).delta() + (d - 1)
    {}

    // Division step: floor(k/n) - floor((k-1)/n) == 1 iff n divides k, else 0
    proof fn lemma_div_step(k: int, n: int) by (nonlinear_arith)
        requires n >= 1,
        ensures k/n - (k-1)/n == if k%n == 0 { 1int } else { 0 }
    {}

    // Leap year correction step: leap_correction(k) - leap_correction(k-1) == 1
    //      iff leap(2000+k), else 0.
    // This connects the from_simple_date formula to dim(y, 2) for the Feb->Mar boundary.
    proof fn lemma_leap_correction_step(k: int)
        ensures leap_correction(k) - leap_correction(k-1)
             == if leap(k + 2000) { 1int } else { 0 }
    {
        lemma_div_step(k, 4);
        assert(k/4 - (k-1)/4 == if k%4 == 0 { 1int } else { 0 });
        lemma_div_step(k, 100);
        assert(k/100 - (k-1)/100 == if k%100 == 0 { 1int } else { 0 });
        lemma_div_step(k, 400);
        assert(k/400 - (k-1)/400 == if k%400 == 0 { 1int } else { 0 });
        assert(leap_correction(k) - leap_correction(k-1)
            == (k/4 - (k-1)/4) - (k/100 - (k-1)/100) + (k/400 - (k-1)/400));
    }

    // Going from the first day of (y,m) to the first day of the next month
    // advances from_simple_date by exactly dim(y,m).
    proof fn lemma_from_simple_date_month_step(y: int, m: int)
        requires 1 <= m <= 12,
        ensures EpochDelta::from_simple_date(SimpleDate(y, m, 1).add_months(1)).delta()
              == EpochDelta::from_simple_date(SimpleDate(y, m, 1)).delta() + dim(y, m)
    {
        // Unfold add_months(1): y_ = y + m/12, m_ = 1 + m%12, d_ = min(1, dim(...)) = 1
        let ny = y + m/12;
        let nm = 1 + m%12;
        assert(SimpleDate(y, m, 1).add_months(1) == SimpleDate(ny, nm, 1));
        // Case split: Feb->Mar crosses a from_simple_date year boundary; all others are arithmetic
        if m == 2 {
            let k = y - 2000;
            lemma_leap_correction_step(k);
        } else {
            // For all other months, years_since_epoch is the same for (y,m) and (ny,nm)
            // so the difference is purely from the (153*m_+2)/5 term = dim(y,m).
        }
    }

    // General lemma: adding n days (positive or negative) shifts from_simple_date delta by n.
    // Induction mirrors add_days' own recursion (same decreases clause).
    pub proof fn lemma_from_simple_date_add_days(date: SimpleDate, n: int)
        requires date.is_valid(),
        ensures EpochDelta::from_simple_date(date.add_days(n)).delta()
              == EpochDelta::from_simple_date(date).delta() + n,
        decreases (n < 0) as nat, abs(n)
    {
        let SimpleDate(y, m, d) = date;
        if 1 <= d + n <= dim(y, m) {
            // ADD-DAYS: result = SimpleDate(y, m, d+n)
            lemma_from_simple_date_day_offset(y, m, d);
            lemma_from_simple_date_day_offset(y, m, d + n);
        } else if d + n > dim(y, m) {
            // ADD-DAYS-OVER: recurse on first-of-next-month with smaller n
            let n_ = n - (dim(y, m) - d) - 1;
            let next = SimpleDate(y, m, 1).add_months(1);
            assert(date.add_days(n) == next.add_days(n_));
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), 1);
            lemma_from_simple_date_add_days(next, n_);
            lemma_from_simple_date_day_offset(y, m, d);
            lemma_from_simple_date_month_step(y, m);
        } else if d > 1 {
            // ADD-DAYS-UNDER1: shift to first-of-month, recurse with smaller |n|
            assert(date.add_days(n) == SimpleDate(y, m, 1).add_days(d - 1 + n));
            lemma_from_simple_date_add_days(SimpleDate(y, m, 1), d - 1 + n);
            lemma_from_simple_date_day_offset(y, m, d);
            lemma_from_simple_date_day_offset(y, m, 1);
        } else {
            // ADD-DAYS-UNDER2: d == 1, step back to previous month
            let SimpleDate(y_, m_, _) = date.add_months(-1);
            let n_ = n + dim(y_, m_);
            assert(date.add_days(n) == SimpleDate(y_, m_, 1).add_days(n_));
            lemma_date_add_months_preserves_validity(date, -1);
            lemma_from_simple_date_add_days(SimpleDate(y_, m_, 1), n_);
            // from_simple_date_first(y, m) == from_simple_date_first(y_, m_) + dim(y_, m_)
            // follows from lemma_from_simple_date_month_step(y_, m_) since SimpleDate(y_, m_, 1).add_months(1) == date
            assert(SimpleDate(y_, m_, 1).add_months(1) == SimpleDate(y, m, 1));
            lemma_from_simple_date_month_step(y_, m_);
            lemma_from_simple_date_day_offset(y, m, 1);
            lemma_from_simple_date_day_offset(y_, m_, 1);
        }
    }


    // Round-trip conversion: from_simple_date(ed.to_ymd()) == ed for all ed
    pub proof fn theorem_epoch_delta_from_simple_date_to_ymd_inverse(ed: EpochDelta)
        ensures EpochDelta::from_simple_date(ed.to_ymd()) == ed
    {
        lemma_epoch_is_at_delta_zero();
        lemma_from_simple_date_add_days(EPOCH, ed.delta());
    }

    // For m1 < m2 in the same year, the first-of-month delta increases by at least dim(y, m1).
    proof fn lemma_from_simple_date_first_of_month_increasing(y: int, m1: int, m2: int)
        requires 1 <= m1, m1 < m2, m2 <= 12,
        ensures EpochDelta::from_simple_date(SimpleDate(y, m2, 1)).delta()
             >= EpochDelta::from_simple_date(SimpleDate(y, m1, 1)).delta() + dim(y, m1),
        decreases m2 - m1,
    {
        lemma_from_simple_date_month_step(y, m1);
        assert(SimpleDate(y, m1, 1).add_months(1) == SimpleDate(y, m1 + 1, 1));
        if m2 > m1 + 1 {
            lemma_from_simple_date_first_of_month_increasing(y, m1 + 1, m2);
        }
    }

    // from_simple_date is strictly monotone on valid dates.
    proof fn lemma_from_simple_date_strict_monotone(d1: SimpleDate, d2: SimpleDate)
        requires d1.is_valid(), d2.is_valid(), d1.lt(d2),
        ensures EpochDelta::from_simple_date(d1).delta() < EpochDelta::from_simple_date(d2).delta(),
    {
        let SimpleDate(y1, m1, dd1) = d1;
        let SimpleDate(y2, m2, dd2) = d2;
        lemma_from_simple_date_day_offset(y1, m1, dd1);
        lemma_from_simple_date_day_offset(y2, m2, dd2);
        if y1 == y2 && m1 == m2 {
            // Same year and month: delta difference = dd2 - dd1 > 0
        } else if y1 == y2 {
            // Same year, m1 < m2
            lemma_from_simple_date_first_of_month_increasing(y1, m1, m2);
            // base(m2) >= base(m1) + dim(y1, m1), and dd1 <= dim(y1, m1), dd2 >= 1
        } else {
            // y1 < y2: chain through year boundaries
            // from_simple_date(SimpleDate(y1, 12, 31)) >= from_simple_date(d1) since m1 <= 12, dd1 <= dim
            lemma_from_simple_date_day_offset(y1, 12, 31);
            if m1 < 12 {
                lemma_from_simple_date_first_of_month_increasing(y1, m1, 12);
            }
            // from_simple_date(SimpleDate(y1+1, 1, 1)) = from_simple_date(SimpleDate(y1, 12, 1)) + 31 by month_step(y1, 12)
            lemma_from_simple_date_month_step(y1, 12);
            assert(SimpleDate(y1, 12, 1).add_months(1) == SimpleDate(y1 + 1, 1, 1));
            // So from_simple_date(SimpleDate(y1+1, 1, 1)) > from_simple_date(SimpleDate(y1, 12, 31))
            // Now chain to (y2, m2, dd2)
            if y2 > y1 + 1 {
                // Induction through intermediate years
                lemma_from_simple_date_cross_year_lower_bound(y1 + 1, y2);
            }
            // from_simple_date(SimpleDate(y2, 1, 1)) <= from_simple_date(SimpleDate(y2, m2, dd2))
            lemma_from_simple_date_day_offset(y2, 1, 1);
            if m2 > 1 {
                lemma_from_simple_date_first_of_month_increasing(y2, 1, m2);
            }
        }
    }

    // One year has >= 365 days.
    proof fn lemma_from_simple_date_one_year_step(y: int)
        ensures EpochDelta::from_simple_date(SimpleDate(y + 1, 1, 1)).delta()
             >= EpochDelta::from_simple_date(SimpleDate(y, 1, 1)).delta() + 365,
    {
        let k = years_since_epoch(y + 1, 1); // = y - 2000
        lemma_leap_correction_step(k);
    }

    proof fn lemma_from_simple_date_cross_year_lower_bound(y1: int, y2: int)
        requires y1 < y2,
        ensures EpochDelta::from_simple_date(SimpleDate(y2, 1, 1)).delta()
             >= EpochDelta::from_simple_date(SimpleDate(y1, 1, 1)).delta() + 365,
        decreases y2 - y1,
    {
        lemma_from_simple_date_one_year_step(y1);
        if y2 > y1 + 1 {
            lemma_from_simple_date_cross_year_lower_bound(y1 + 1, y2);
        }
    }

    // The other round-trip: to_ymd(from_simple_date(d)) == d for valid dates.
    // Follows from the first round-trip + injectivity of from_simple_date.
    pub proof fn theorem_epoch_delta_to_ymd_from_simple_date_inverse(d: SimpleDate)
        requires d.is_valid(),
        ensures EpochDelta::to_ymd(EpochDelta::from_simple_date(d)) == d,
    {
        let ed = EpochDelta::from_simple_date(d);
        let d2 = ed.to_ymd(); // = EPOCH.add_days(from_simple_date(d).delta())
        // from_simple_date(to_ymd(ed)) == ed, so from_simple_date(d2) == from_simple_date(d)
        theorem_epoch_delta_from_simple_date_to_ymd_inverse(ed);
        // d2 is valid since EPOCH is valid and add_days preserves validity
        lemma_date_add_days_preserves_validity(EPOCH, ed.delta());
        // d and d2 are both valid with from_simple_date(d) == from_simple_date(d2), so d == d2 by injectivity
        theorem_epoch_delta_congruent_preserves_comparison(d, ed, d2, EpochDelta::from_simple_date(d2));
    }

    pub proof fn theorem_epoch_delta_congruent_preserves_comparison(d1: SimpleDate, ed1: EpochDelta, d2: SimpleDate, ed2: EpochDelta)
        requires d1.is_valid(), d2.is_valid(), ed_congruent(d1, ed1), ed_congruent(d2, ed2),
        ensures
            (d1.lt(d2) <==> ed1.lt(ed2)),
            (d1.eq(d2)  <==> ed1.eq(ed2)),
    {
        // ed1 == from_simple_date(d1), ed2 == from_simple_date(d2) by definition of congruent
        lemma_date_lt_is_total(d1, d2);
        if d1.lt(d2) {
            lemma_from_simple_date_strict_monotone(d1, d2);
        }
        if d2.lt(d1) {
            lemma_from_simple_date_strict_monotone(d2, d1);
        }
        // All four ensures clauses follow:
        // d1.lt(d2) ==> delta(d1) < delta(d2) ==> ed1.lt(ed2)          [strict mono]
        // ed1.lt(ed2) ==> delta(d1) < delta(d2) ==> !d2.lt(d1) && d1 != d2 ==> d1.lt(d2) [totality + contrapositive]
        // d1 == d2 ==> from_simple_date(d1) == from_simple_date(d2) ==> ed1 == ed2     [trivial]
        // ed1 == ed2 ==> delta equal ==> !d1.lt(d2) && !d2.lt(d1) ==> d1 == d2 [totality + contrapositive]
    }

    // Congruence is preserved under period addition.
    pub proof fn theorem_epoch_delta_add_period_preserves_congruence(d: SimpleDate, ed: EpochDelta, p: Period)
        requires d.is_valid(), ed_congruent(d, ed),
        ensures ed_congruent(d.add_period(p), ed.add_period(p)),
    {
        // ed == from_simple_date(d) by definition of congruent.
        // Goal: from_simple_date(d.add_period(p)) == ed.add_period(p).
        let n = p.years() * 12 + p.months();
        let days = p.days();

        // Step 1: d == ed.to_ymd() (the other round-trip)
        theorem_epoch_delta_to_ymd_from_simple_date_inverse(d);
        assert(d == ed.to_ymd());

        // Step 2: d.add_months(n) is valid
        lemma_date_add_months_preserves_validity(d, n);

        // Step 3: from_simple_date(d.add_months(n).add_days(days)).delta()
        //       == from_simple_date(d.add_months(n)).delta() + days
        lemma_from_simple_date_add_days(d.add_months(n), days);

        // Step 4: ed.add_period(p)
        //       = ed.add_months(n).add_days(days)
        //       = EpochDelta(from_simple_date(ed.to_ymd().add_months(n)).delta() + days)
        //       = EpochDelta(from_simple_date(d.add_months(n)).delta() + days)   [since d == ed.to_ymd()]
        //       = from_simple_date(d.add_months(n).add_days(days))                [by step 3]
        //       = from_simple_date(d.add_period(p))
    }

} // verus!
