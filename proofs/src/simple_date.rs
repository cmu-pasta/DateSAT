use vstd::prelude::*;
use crate::*;
use crate::period::*;

verus! {

    /// The Simple encoding: a simple baseline encoding used by the Python solver.
    /// Dates are (year, month, day) triples, and days are added one at a time.
    pub struct SimpleDate(pub int, pub int, pub int);

    impl SimpleDate {
        pub open spec fn year(self) -> int {
            self.0
        }

        pub open spec fn month(self) -> int {
            self.1
        }

        pub open spec fn day(self) -> int {
            self.2
        }

        /// Lexicographic strict ordering on dates: year, then month, then day.
        pub open spec fn lt(self, other: Self) -> bool {
            self.year() < other.year() ||
            (self.year() == other.year() && self.month() < other.month()) ||
            (self.year() == other.year() && self.month() == other.month() && self.day() < other.day())
        }

        /// Equality: component-wise comparison.
        pub open spec fn eq(self, other: Self) -> bool {
            self.year() == other.year() && self.month() == other.month() && self.day() == other.day()
        }

        /// Add n months, clamping the day to the new month's dim.
        pub open spec fn add_months(self, n: int) -> SimpleDate {
            let SimpleDate(y, m, d) = self;
            let y_ = y + (m - 1 + n) / 12;
            let m_ = 1 + ((m - 1 + n) % 12);
            let d_ = if d < 1 { 1 } else if d > dim(y_, m_) { dim(y_, m_) } else { d };
            SimpleDate(y_, m_, d_)
        }

        /// One day forward: overflow to the 1st of the next month (with year wrap).
        pub open spec fn succ(self) -> SimpleDate {
            let SimpleDate(y, m, d) = self;
            if d + 1 > dim(y, m) {
                if m + 1 > 12 { SimpleDate(y + 1, 1, 1) } else { SimpleDate(y, m + 1, 1) }
            } else {
                SimpleDate(y, m, d + 1)
            }
        }

        /// One day backward: underflow to the last day of the previous month (with year wrap).
        pub open spec fn pred(self) -> SimpleDate {
            let SimpleDate(y, m, d) = self;
            let py = if m - 1 < 1 { y - 1 } else { y };
            let pm = if m - 1 < 1 { 12 } else { m - 1 };
            if d - 1 < 1 {
                SimpleDate(py, pm, dim(py, pm))
            } else {
                SimpleDate(y, m, d - 1)
            }
        }

        /// Add n days by unit steps: |n| applications of succ (n > 0) or pred (n < 0).
        pub open spec fn add_days(self, n: int) -> SimpleDate
            decreases abs(n)
        {
            if n > 0 {
                self.succ().add_days(n - 1)
            } else if n < 0 {
                self.pred().add_days(n + 1)
            } else {
                self
            }
        }

        /// Add a calendar period. Days-only periods skip the month step (fast path).
        pub open spec fn add_period(self, period: Period) -> SimpleDate {
            if period.years() == 0 && period.months() == 0 {
                self.add_days(period.days())
            } else {
                self.add_months(period.years() * 12 + period.months()).add_days(period.days())
            }
        }
    }

    impl DateEncoding for SimpleDate {
        open spec fn from_ymd(y: int, m: int, d: int) -> SimpleDate {
            SimpleDate(y, m, d)
        }

        open spec fn year(self) -> int {
            self.year()
        }

        open spec fn month(self) -> int {
            self.month()
        }

        open spec fn day(self) -> int {
            self.day()
        }

        open spec fn lt(self, other: Self) -> bool {
            self.lt(other)
        }

        open spec fn eq(self, other: Self) -> bool {
            self.eq(other)
        }

        open spec fn add_period(self, period: Period) -> SimpleDate {
            self.add_period(period)
        }
    }

    // ── Congruence with the semantics ──────────────────────────────────

    pub open spec fn sd_congruent(d: Date, sd: SimpleDate) -> bool {
        sd == SimpleDate::from_ymd(d.year(), d.month(), d.day())
    }

    pub proof fn theorem_simple_date_from_ymd_congruent(y: int, m: int, d: int)
        ensures sd_congruent(Date::from_ymd(y, m, d), SimpleDate::from_ymd(y, m, d)),
    {
    }

    pub proof fn theorem_simple_date_congruent_preserves_comparison(d1: Date, sd1: SimpleDate, d2: Date, sd2: SimpleDate)
        requires sd_congruent(d1, sd1), sd_congruent(d2, sd2),
        ensures
            (d1.lt(d2) <==> sd1.lt(sd2)),
            (d1.eq(d2) <==> sd1.eq(sd2)),
    {
    }

    // ── Unit-step day addition agrees with the semantics ───────────────

    /// Adding 0 days is the identity on valid dates.
    proof fn lemma_date_add_days_zero(d: Date)
        requires d.is_valid(),
        ensures d.add_days(0) == d,
    {
        // ADD-DAYS rule with n == 0
    }

    /// Adding 0 months is the identity on valid dates.
    proof fn lemma_date_add_months_zero(d: Date)
        requires d.is_valid(),
        ensures d.add_months(0) == d,
    {
        // (m - 1) / 12 == 0 and (m - 1) % 12 == m - 1 since 1 <= m <= 12
    }

    /// Day additions compose: (d + a days) + b days == d + (a + b) days.
    proof fn lemma_date_add_days_compose(d: Date, a: int, b: int)
        requires d.is_valid(),
        ensures d.add_days(a).add_days(b) == d.add_days(a + b),
    {
        let x = d.add_days(a).add_days(b);
        let z = d.add_days(a + b);
        // Both sides are valid ...
        lemma_date_add_days_preserves_validity(d, a);
        lemma_date_add_days_preserves_validity(d.add_days(a), b);
        lemma_date_add_days_preserves_validity(d, a + b);
        // ... and have the same epoch delta ...
        lemma_from_date_add_days(d, a);
        lemma_from_date_add_days(d.add_days(a), b);
        lemma_from_date_add_days(d, a + b);
        assert(EpochDelta::from_date(x) == EpochDelta::from_date(z));
        // ... so they are equal by injectivity of from_date.
        theorem_epoch_delta_to_ymd_from_date_inverse(x);
        theorem_epoch_delta_to_ymd_from_date_inverse(z);
    }

    /// succ is the semantics' +1 day.
    proof fn lemma_succ_is_add_one(d: Date)
        requires d.is_valid(),
        ensures SimpleDate(d.0, d.1, d.2).succ() == ({ let r = d.add_days(1); SimpleDate(r.0, r.1, r.2) }),
    {
        let Date(y, m, dd) = d;
        if dd + 1 > dim(y, m) {
            // ADD-DAYS-OVER: first of next month, plus 0 days
            let next = Date(y, m, 1).add_months(1);
            assert(d.add_days(1) == next.add_days(0));
            lemma_date_add_months_preserves_validity(Date(y, m, 1), 1);
            lemma_date_add_days_zero(next);
            if m == 12 {
                assert(next == Date(y + 1, 1, 1));
            } else {
                assert(next == Date(y, m + 1, 1));
            }
        }
    }

    /// pred is the semantics' -1 day.
    proof fn lemma_pred_is_sub_one(d: Date)
        requires d.is_valid(),
        ensures SimpleDate(d.0, d.1, d.2).pred() == ({ let r = d.add_days(-1); SimpleDate(r.0, r.1, r.2) }),
    {
        let Date(y, m, dd) = d;
        if dd == 1 {
            // ADD-DAYS-UNDER2: last day of the previous month
            let Date(y_, m_, _) = d.add_months(-1);
            if m == 1 {
                assert(y_ == y - 1 && m_ == 12);
            } else {
                assert(y_ == y && m_ == m - 1);
            }
            lemma_dim_is_bounded(y_, m_);
            assert(d.add_days(-1) == Date(y_, m_, 1).add_days(dim(y_, m_) - 1));
        }
    }

    /// Unit-step day addition (|n| succ/pred steps) equals the semantics' add_days.
    pub proof fn theorem_simple_date_add_days_congruent(d: Date, n: int)
        requires d.is_valid(),
        ensures sd_congruent(d.add_days(n), SimpleDate(d.0, d.1, d.2).add_days(n)),
        decreases abs(n)
    {
        if n > 0 {
            // One succ step, then n - 1 more
            let d1 = d.add_days(1);
            lemma_succ_is_add_one(d);
            lemma_date_add_days_preserves_validity(d, 1);
            theorem_simple_date_add_days_congruent(d1, n - 1);
            lemma_date_add_days_compose(d, 1, n - 1);
        } else if n < 0 {
            // One pred step, then n + 1 more
            let d1 = d.add_days(-1);
            lemma_pred_is_sub_one(d);
            lemma_date_add_days_preserves_validity(d, -1);
            theorem_simple_date_add_days_congruent(d1, n + 1);
            lemma_date_add_days_compose(d, -1, n + 1);
        } else {
            lemma_date_add_days_zero(d);
        }
    }

    /// Month addition agrees with the semantics on valid dates.
    proof fn lemma_simple_date_add_months_congruent(d: Date, n: int)
        requires d.is_valid(),
        ensures sd_congruent(d.add_months(n), SimpleDate(d.0, d.1, d.2).add_months(n)),
    {
        // Same formula as the semantics; the d < 1 branch is dead since d >= 1
    }

    // Congruence is preserved under period addition.
    pub proof fn theorem_simple_date_add_period_preserves_congruence(d: Date, sd: SimpleDate, p: Period)
        requires d.is_valid(), sd_congruent(d, sd),
        ensures sd_congruent(d.add_period(p), sd.add_period(p)),
    {
        let n = p.years() * 12 + p.months();
        assert(sd == SimpleDate(d.0, d.1, d.2));
        if p.years() == 0 && p.months() == 0 {
            // Fast path: the semantics' add_months(0) is the identity
            lemma_date_add_months_zero(d);
            theorem_simple_date_add_days_congruent(d, p.days());
        } else {
            lemma_simple_date_add_months_congruent(d, n);
            lemma_date_add_months_preserves_validity(d, n);
            theorem_simple_date_add_days_congruent(d.add_months(n), p.days());
        }
    }

} // verus!
