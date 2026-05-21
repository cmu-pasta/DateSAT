use vstd::prelude::*;
use vstd::math::*;
use crate::*;
use crate::period::*;

verus! {

    /// A calendar date in (year, month, day) form.
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

        /// Non-strict ordering: less-than or equal.
        pub open spec fn leq(self, other: Self) -> bool {
            self.lt(other) || self == other
        }

        /// A date is valid when its month is in 1..12 and its day is in 1..dim(year, month).
        pub open spec fn is_valid(self) -> bool {
            1 <= self.month() <= 12 && 1 <= self.day() <= dim(self.year(), self.month())
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

    /// Whether a year is a leap year (Gregorian rule).
    pub open spec fn leap(year: int) -> bool {
        year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
    }

    /// Days in month: the number of days in the given month of the given year.
    pub open spec fn dim(year: int, month: int) -> int {
        let calendar = [31, if leap(year) { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        calendar[month - 1]
    }

    // ── SimpleDate and calendar proofs ──────────────────────────────────────

    pub proof fn lemma_dim_is_bounded(year: int, month: int)
        requires 1 <= month <= 12,
        ensures 28 <= dim(year, month) <= 31
    {
        // QED
    }

    proof fn lemma_epoch_is_valid() {
        EPOCH.is_valid();
    }

    pub proof fn lemma_date_leq_is_reflexive(d: SimpleDate)
        ensures d.leq(d) {}

    pub proof fn lemma_date_leq_is_transitive(d1: SimpleDate, d2: SimpleDate, d3: SimpleDate)
        requires d1.leq(d2) && d2.leq(d3),
        ensures d1.leq(d3) {}

    proof fn lemma_date_leq_is_antisymmetric(d1: SimpleDate, d2: SimpleDate)
        requires d1.leq(d2) && d2.leq(d1),
        ensures d1 == d2 {}

    proof fn lemma_date_lt_is_irreflexive(d: SimpleDate)
        ensures !d.lt(d) {}

    proof fn lemma_date_lt_is_asymmetric(d1: SimpleDate, d2: SimpleDate)
        requires d1.lt(d2),
        ensures !d2.lt(d1) {}

    proof fn lemma_date_lt_is_transitive(d1: SimpleDate, d2: SimpleDate, d3: SimpleDate)
        requires d1.lt(d2) && d2.lt(d3),
        ensures d1.lt(d3) {}

    pub proof fn lemma_date_lt_implies_leq(d1: SimpleDate, d2: SimpleDate)
        requires d1.lt(d2),
        ensures d1.leq(d2) {}

    proof fn lemma_date_lt_implies_neq(d1: SimpleDate, d2: SimpleDate)
        requires d1.lt(d2),
        ensures d1 != d2 {}

    proof fn lemma_date_leq_neq_implies_lt(d1: SimpleDate, d2: SimpleDate)
        requires d1.leq(d2) && d1 != d2,
        ensures d1.lt(d2) {}

    pub proof fn lemma_date_lt_is_total(d1: SimpleDate, d2: SimpleDate)
        ensures d1 == d2 || d1.lt(d2) || d2.lt(d1)
    {}

    // ── SimpleDate-period arithmetic ────────────────────────────────────────

    impl SimpleDate {
        /// Add n months to a date, clamping the day to the new month's dim.
        pub open spec fn add_months(self, n: int) -> SimpleDate {
            let SimpleDate(y, m, d) = self;
            let y_ = y + (m - 1 + n) / 12;
            let m_ = 1 + ((m - 1 + n) % 12);
            let d_ = min(d, dim(y_, m_));
            SimpleDate(y_, m_, d_)
        }

        /// Add n days to a date (positive or negative), recursively stepping
        /// across month boundaries using the ADD-DAYS-OVER / ADD-DAYS-UNDER rules.
        pub open spec fn add_days(self, n: int) -> SimpleDate
            recommends self.is_valid(),
            decreases (n < 0) as nat, abs(n) // see note for ADD-DAYS-UNDER-2
        {
            let SimpleDate(y, m, d) = self;

            if 1 <= d <= dim(y, m) {
                if 1 <= d + n <= dim(y, m) {
                    // ADD_DAYS rule
                    SimpleDate(y, m, d + n)
                } else if (d + n > dim(y, m)) {
                    // ADD-DAYS-OVER rule
                    SimpleDate(y, m, 1).add_months(1).add_days(n - (dim(y, m) - d) - 1)
                } else if d > 1 {
                    // ADD-DAYS-UNDER1 rule
                    //assert(d + n <= 0); // covered all positive cases above
                    SimpleDate(y, m, 1).add_days(d - 1 + n)
                } else {
                    // ADD-DAYS-UNDER2 rule
                    // assert(d == 1);
                    // assert(1 + n <= 0);
                    let SimpleDate(y_, m_, _) = self.add_months(-1);
                    SimpleDate(y_, m_, 1).add_days(n + dim(y_, m_))
                    // Note: Proving that this case actually does cause
                    // recursion to terminate is tricky. For example, if we
                    // are adding -70 days, then recursively could go down to
                    // -39 days, -9 days, and then +21 days!! But we know that
                    // once we are adding positive number of days, the
                    // ADD-DAYS/ADD-DAYS-OVER rules always reduce down to zero.
                    // So, the `decreases` clause in the spec takes into account
                    // both the sign of `n` and its absolute value.
                }
             } else {
                SimpleDate(0, 0, 0) // spec is undefined for invalid dates
            }

        }

        /// Add a calendar period: first add years/months (as months), then add days.
        pub open spec fn add_period(self, period: Period) -> SimpleDate
        {
            self.add_months(period.years() * 12 + period.months()).add_days(period.days())
        }
    }

    // ── SimpleDate-period arithmetic proofs ─────────────────────────────────

    pub proof fn lemma_date_add_months_preserves_validity(date: SimpleDate, n: int)
        requires date.is_valid(),
        ensures date.add_months(n).is_valid()
    {
        // QED
    }

    proof fn lemma_date_add_days_pos_preserves_validity(date: SimpleDate, n: int)
        requires date.is_valid() && n >= 0,
        ensures date.add_days(n).is_valid(),
        decreases n
    {
        let SimpleDate(y, m, d) = date;
        if 1 <= d + n <= dim(y, m) {
            // Base case: ADD-DAYS rule; trivially valid
        } else {
            // ADD-DAYS-OVER rule
            assert(d + n > dim(y, m));
            let n_ = n - (dim(y, m) - d) - 1;
            lemma_date_add_days_pos_preserves_validity(SimpleDate(y, m, 1).add_months(1), n_);
        }
    }

    proof fn lemma_date_add_days_neg_preserves_validity(date: SimpleDate, n: int)
        requires date.is_valid() && n < 0,
        ensures date.add_days(n).is_valid(),
        decreases abs(n)
    {
        let SimpleDate(y, m, d) = date;
        if 1 <= d + n {
            // Base case: ADD-DAYS rule
            assert(d + n <= dim(y, m)); // since date.is_valid() && n < 0
        } else if d > 1 {
            // ADD-DAYS-UNDER1 rule
            assert(d <= dim(y, m));
            assert(d + n <= 0);
            lemma_date_add_days_neg_preserves_validity(SimpleDate(y, m, 1), d - 1 + n);
        } else {
            // ADD-DAYS-UNDER2 rule
            assert(d == 1);
            assert(d <= dim(y, m));
            let SimpleDate(y_, m_, _) = date.add_months(-1);
            let n_ = n + dim(y_, m_);
            // Split into positive and negative cases when recursing
            if n_ >= 0 {
                lemma_date_add_days_pos_preserves_validity(SimpleDate(y_, m_, 1), n_)
            } else {
                lemma_date_add_days_neg_preserves_validity(SimpleDate(y_, m_, 1), n_)
            }
        }
    }

    pub proof fn lemma_date_add_days_preserves_validity(date: SimpleDate, n: int)
        requires date.is_valid(),
        ensures date.add_days(n).is_valid()
    {
        if n < 0 {
            lemma_date_add_days_neg_preserves_validity(date, n);
        } else {
            lemma_date_add_days_pos_preserves_validity(date, n);
        }
    }

    pub proof fn theorem_date_add_period_preserves_validity(date: SimpleDate, period: Period)
        requires date.is_valid(),
        ensures date.add_period(period).is_valid()
    {
        let months_to_add = period.years() * 12 + period.months();
        lemma_date_add_months_preserves_validity(date, months_to_add);
        let d_ = date.add_months(months_to_add);
        lemma_date_add_days_preserves_validity(d_, period.days());
    }

} // verus!
