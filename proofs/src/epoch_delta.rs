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

        /// Convert an epoch delta to a YMD date using a closed-form formula.
        ///
        /// The formula inverts from_date in four steps:
        ///   1. Split the delta into 400-year cycles (eras) and a day of the era.
        ///   2. Recover the March-based year of the era from the day of the era.
        ///   3. Recover the day of that year.
        ///   4. Recover the month and day by inverting (153 * me + 2) / 5.
        pub open spec fn to_ymd(self) -> Date
            recommends EPOCH == Date(2000, 3, 1) // the logic depends on the specific value of EPOCH
        {
            let era = self.delta() / 146097;
            let doe = self.delta() % 146097;
            let yoe = year_of_era(doe);
            let doy = doe - days_before_year_of_era(yoe);
            let me = (5 * doy + 2) / 153;
            let d = doy - (153 * me + 2) / 5 + 1;
            let m = if me < 10 { me + 3 } else { me - 9 };
            let y = 2000 + 400 * era + yoe + (if m <= 2 { 1int } else { 0 });
            Date(y, m, d)
        }

        /// Convert a YMD date to an epoch delta using a closed-form formula.
        ///
        /// The formula counts days from EPOCH (2000-03-01) in three parts:
        ///   1. Days contributed by full years elapsed since the epoch.
        ///   2. Days contributed by full months elapsed since March.
        ///   3. Days elapsed within the current calendar month.
        pub open spec fn from_date(date: Date) -> EpochDelta
            recommends EPOCH == Date(2000, 3, 1) // the logic depends on the specific value of EPOCH
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
            EpochDelta::from_date(self.to_ymd().add_months(n))
        }

        /// Add a calendar period: first add years/months, then add days.
        pub open spec fn add_period(self, period: Period) -> EpochDelta {
            self.add_months(period.years() * 12 + period.months()).add_days(period.days())
        }
    }

    impl DateEncoding for EpochDelta {
        open spec fn from_ymd(y: int, m: int, d: int) -> EpochDelta {
            EpochDelta::from_date(Date(y, m, d))
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

    // ── Helper spec functions for the from_date formula ─────────────────

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

    /// March-based year within a 400-year era (0..399), given the day of the era (0..146096).
    /// Subtracting doe/1460, adding doe/36524 and subtracting doe/146096 removes the
    /// leap days elapsed so far, so that the result can be divided by 365.
    pub open spec fn year_of_era(doe: int) -> int {
        (doe - doe/1460 + doe/36524 - doe/146096) / 365
    }

    /// Days in an era before the start of its March-based year yoe (0..399).
    pub open spec fn days_before_year_of_era(yoe: int) -> int {
        365*yoe + yoe/4 - yoe/100
    }

    // ── EpochDelta congruence proofs ───────────────────────────────────

    // The EPOCH is at delta = 0
    pub proof fn lemma_epoch_is_at_delta_zero() ensures
        EpochDelta::from_date(EPOCH).delta() == 0 {}

    // A date with delta = 0 is the EPOCH
    pub proof fn lemma_delta_zero_is_epoch() ensures
        EpochDelta::to_ymd(EpochDelta(0)) == EPOCH {}

    /// Congruence between Date and EpochDelta: asserts they are related by from_ymd.
    /// Whether this relation preserves comparison and arithmetic is proven below.
    pub open spec fn ed_congruent(d: Date, ed: EpochDelta) -> bool {
        ed == EpochDelta::from_ymd(d.year(), d.month(), d.day())
    }

    // Congruence at construction: from_ymd is congruent with Date.
    pub proof fn theorem_epoch_delta_from_ymd_congruent(y: int, m: int, d: int)
        ensures ed_congruent(Date(y, m, d), EpochDelta::from_ymd(y, m, d)),
    {}

    // The from_date delta for any date = first-of-month value + (day - 1)
    proof fn lemma_from_date_day_offset(y: int, m: int, d: int)
        ensures EpochDelta::from_date(Date(y, m, d)).delta()
        == EpochDelta::from_date(Date(y, m, 1)).delta() + (d - 1)
    {}

    // Division step: floor(k/n) - floor((k-1)/n) == 1 iff n divides k, else 0
    proof fn lemma_div_step(k: int, n: int) by (nonlinear_arith)
        requires n >= 1,
        ensures k/n - (k-1)/n == if k%n == 0 { 1int } else { 0 }
    {}

    // Leap year correction step: leap_correction(k) - leap_correction(k-1) == 1
    //      iff leap(2000+k), else 0.
    // This connects the from_date formula to dim(y, 2) for the Feb->Mar boundary.
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
    // advances from_date by exactly dim(y,m).
    proof fn lemma_from_date_month_step(y: int, m: int)
        requires 1 <= m <= 12,
        ensures EpochDelta::from_date(Date(y, m, 1).add_months(1)).delta()
              == EpochDelta::from_date(Date(y, m, 1)).delta() + dim(y, m)
    {
        // Unfold add_months(1): y_ = y + m/12, m_ = 1 + m%12, d_ = min(1, dim(...)) = 1
        let ny = y + m/12;
        let nm = 1 + m%12;
        assert(Date(y, m, 1).add_months(1) == Date(ny, nm, 1));
        // Case split: Feb->Mar crosses a from_date year boundary; all others are arithmetic
        if m == 2 {
            let k = y - 2000;
            lemma_leap_correction_step(k);
        } else {
            // For all other months, years_since_epoch is the same for (y,m) and (ny,nm)
            // so the difference is purely from the (153*m_+2)/5 term = dim(y,m).
        }
    }

    // General lemma: adding n days (positive or negative) shifts from_date delta by n.
    // Induction mirrors add_days' own recursion (same decreases clause).
    pub proof fn lemma_from_date_add_days(date: Date, n: int)
        requires date.is_valid(),
        ensures EpochDelta::from_date(date.add_days(n)).delta()
              == EpochDelta::from_date(date).delta() + n,
        decreases (n < 0) as nat, abs(n)
    {
        let Date(y, m, d) = date;
        if 1 <= d + n <= dim(y, m) {
            // ADD-DAYS: result = Date(y, m, d+n)
            lemma_from_date_day_offset(y, m, d);
            lemma_from_date_day_offset(y, m, d + n);
        } else if d + n > dim(y, m) {
            // ADD-DAYS-OVER: recurse on first-of-next-month with smaller n
            let n_ = n - (dim(y, m) - d) - 1;
            let next = Date(y, m, 1).add_months(1);
            assert(date.add_days(n) == next.add_days(n_));
            lemma_date_add_months_preserves_validity(Date(y, m, 1), 1);
            lemma_from_date_add_days(next, n_);
            lemma_from_date_day_offset(y, m, d);
            lemma_from_date_month_step(y, m);
        } else if d > 1 {
            // ADD-DAYS-UNDER1: shift to first-of-month, recurse with smaller |n|
            assert(date.add_days(n) == Date(y, m, 1).add_days(d - 1 + n));
            lemma_from_date_add_days(Date(y, m, 1), d - 1 + n);
            lemma_from_date_day_offset(y, m, d);
            lemma_from_date_day_offset(y, m, 1);
        } else {
            // ADD-DAYS-UNDER2: d == 1, step back to previous month
            let Date(y_, m_, _) = date.add_months(-1);
            let n_ = n + dim(y_, m_);
            assert(date.add_days(n) == Date(y_, m_, 1).add_days(n_));
            lemma_date_add_months_preserves_validity(date, -1);
            lemma_from_date_add_days(Date(y_, m_, 1), n_);
            // from_date_first(y, m) == from_date_first(y_, m_) + dim(y_, m_)
            // follows from lemma_from_date_month_step(y_, m_) since Date(y_, m_, 1).add_months(1) == date
            assert(Date(y_, m_, 1).add_months(1) == Date(y, m, 1));
            lemma_from_date_month_step(y_, m_);
            lemma_from_date_day_offset(y, m, 1);
            lemma_from_date_day_offset(y_, m_, 1);
        }
    }


    // ── Closed-form to_ymd proofs ──────────────────────────────────────

    // Every day of an era splits into 100-year blocks (c), 4-year blocks (q),
    // years (s) and a day of the year (r). The day of the year can only be 365
    // in a leap year, which is the last year of a 4-year block, unless that
    // block ends a century that is not the last one of the era.
    proof fn lemma_era_block_decomposition(doe: int) -> (res: (int, int, int, int))
        requires 0 <= doe < 146097,
        ensures ({
            let (c, q, s, r) = res;
            &&& 0 <= c <= 3 && 0 <= q <= 24 && 0 <= s <= 3 && 0 <= r
            &&& doe == 36524*c + 1461*q + 365*s + r
            &&& r <= if s == 3 && (q != 24 || c == 3) { 365int } else { 364 }
        })
    {
        let c = if doe / 36524 > 3 { 3 } else { doe / 36524 };
        let rc = doe - 36524*c;
        let q = rc / 1461;
        let rq = rc % 1461;
        let s = if rq / 365 > 3 { 3 } else { rq / 365 };
        let r = rq - 365*s;
        (c, q, s, r)
    }

    // year_of_era recovers the year from its block decomposition,
    // and the remainder is the day of that year.
    proof fn lemma_year_of_era(doe: int, c: int, q: int, s: int, r: int)
        requires
            0 <= c <= 3, 0 <= q <= 24, 0 <= s <= 3, 0 <= r,
            doe == 36524*c + 1461*q + 365*s + r,
            r <= if s == 3 && (q != 24 || c == 3) { 365int } else { 364 },
        ensures
            year_of_era(doe) == 100*c + 4*q + s,
            doe - days_before_year_of_era(100*c + 4*q + s) == r,
    {
        let yoe = 100*c + 4*q + s;
        // Late in a 4-year block, doe/1460 counts one block too many.
        // This happens on day 365 of a leap year, and never on day 0,
        // so the remainder r - e still lies in 0..364.
        let e = if 24*c + q + 365*s + r >= 1460 { 1int } else { 0 };
        // Only the last day of the era reaches a fifth century or a full era.
        let z = if doe == 146096 { 1int } else { 0 };
        assert(doe == 1460*(25*c + q + e) + (24*c + q + 365*s + r - 1460*e));
        assert(doe / 1460 == 25*c + q + e);
        assert(doe / 36524 == c + z);
        assert(doe / 146096 == z);
        assert(doe - doe/1460 + doe/36524 - doe/146096 == 365*yoe + r - e);
        assert(year_of_era(doe) == yoe);
        assert(yoe / 4 == 25*c + q);
        assert(yoe / 100 == c);
    }

    // The month/day formula yields a valid day of the month for any day of a March-based year.
    proof fn lemma_month_day_of_doy(doy: int, y: int)
        requires 0 <= doy <= if leap(y) { 365int } else { 364 },
        ensures ({
            let me = (5 * doy + 2) / 153;
            let d = doy - (153 * me + 2) / 5 + 1;
            let m = if me < 10 { me + 3 } else { me - 9 };
            &&& 0 <= me <= 11
            &&& 1 <= d <= dim(y, m)
        })
    {
        let me = (5 * doy + 2) / 153;
        // Each month me starts on day (153 * me + 2) / 5 of the year
        assert(153*me <= 5*doy + 2 < 153*me + 153);
        assert(0 <= me <= 11);
        assert(me == 0 || me == 1 || me == 2 || me == 3 || me == 4 || me == 5
            || me == 6 || me == 7 || me == 8 || me == 9 || me == 10 || me == 11);
    }

    // to_ymd always yields a valid date.
    pub proof fn lemma_to_ymd_is_valid(ed: EpochDelta)
        ensures ed.to_ymd().is_valid(),
    {
        let era = ed.delta() / 146097;
        let doe = ed.delta() % 146097;
        let (c, q, s, r) = lemma_era_block_decomposition(doe);
        lemma_year_of_era(doe, c, q, s, r);
        // The year in which this March-based year's February falls
        let y = 2000 + 400*era + 100*c + 4*q + s + 1;
        if s == 3 && (q != 24 || c == 3) {
            assert(y == 4 * (501 + 100*era + 25*c + q));
            assert(y % 4 == 0);
            if q == 24 {
                assert(y == 400 * (6 + era));
                assert(y % 400 == 0);
            } else {
                assert(y == 100 * (20 + 4*era + c) + 4*(q + 1));
                assert(y % 100 == 4*(q + 1));
            }
            assert(leap(y));
        }
        lemma_month_day_of_doy(r, y);
    }

    // Round-trip conversion: from_date(ed.to_ymd()) == ed for all ed
    pub proof fn theorem_epoch_delta_from_date_to_ymd_inverse(ed: EpochDelta)
        ensures EpochDelta::from_date(ed.to_ymd()) == ed
    {
        let era = ed.delta() / 146097;
        let doe = ed.delta() % 146097;
        let (c, q, s, r) = lemma_era_block_decomposition(doe);
        lemma_year_of_era(doe, c, q, s, r);
        let yoe = 100*c + 4*q + s;
        let d = ed.to_ymd();
        // from_date sees the same March-based year and month that to_ymd produced ...
        assert(years_since_epoch(d.year(), d.month()) == 400*era + yoe);
        assert(months_since_march(d.month()) == (5 * r + 2) / 153);
        // ... and each era contributes exactly 146097 days.
        let ye = 400*era + yoe;
        assert(ye / 4 == 100*era + yoe / 4);
        assert(ye / 100 == 4*era + yoe / 100);
        assert(ye / 400 == era);
        assert(365*ye + leap_correction(ye) == 146097*era + days_before_year_of_era(yoe));
    }

    // to_ymd agrees with adding delta days to the EPOCH under the semantics.
    pub proof fn lemma_to_ymd_is_epoch_add_days(ed: EpochDelta)
        ensures ed.to_ymd() == EPOCH.add_days(ed.delta()),
    {
        let d1 = ed.to_ymd();
        let d2 = EPOCH.add_days(ed.delta());
        lemma_to_ymd_is_valid(ed);
        lemma_date_add_days_preserves_validity(EPOCH, ed.delta());
        theorem_epoch_delta_from_date_to_ymd_inverse(ed);
        lemma_epoch_is_at_delta_zero();
        lemma_from_date_add_days(EPOCH, ed.delta());
        theorem_epoch_delta_congruent_preserves_comparison(d1, ed, d2, ed);
    }

    // For m1 < m2 in the same year, the first-of-month delta increases by at least dim(y, m1).
    proof fn lemma_from_date_first_of_month_increasing(y: int, m1: int, m2: int)
        requires 1 <= m1, m1 < m2, m2 <= 12,
        ensures EpochDelta::from_date(Date(y, m2, 1)).delta()
             >= EpochDelta::from_date(Date(y, m1, 1)).delta() + dim(y, m1),
        decreases m2 - m1,
    {
        lemma_from_date_month_step(y, m1);
        assert(Date(y, m1, 1).add_months(1) == Date(y, m1 + 1, 1));
        if m2 > m1 + 1 {
            lemma_from_date_first_of_month_increasing(y, m1 + 1, m2);
        }
    }

    // from_date is strictly monotone on valid dates.
    proof fn lemma_from_date_strict_monotone(d1: Date, d2: Date)
        requires d1.is_valid(), d2.is_valid(), d1.lt(d2),
        ensures EpochDelta::from_date(d1).delta() < EpochDelta::from_date(d2).delta(),
    {
        let Date(y1, m1, dd1) = d1;
        let Date(y2, m2, dd2) = d2;
        lemma_from_date_day_offset(y1, m1, dd1);
        lemma_from_date_day_offset(y2, m2, dd2);
        if y1 == y2 && m1 == m2 {
            // Same year and month: delta difference = dd2 - dd1 > 0
        } else if y1 == y2 {
            // Same year, m1 < m2
            lemma_from_date_first_of_month_increasing(y1, m1, m2);
            // base(m2) >= base(m1) + dim(y1, m1), and dd1 <= dim(y1, m1), dd2 >= 1
        } else {
            // y1 < y2: chain through year boundaries
            // from_date(Date(y1, 12, 31)) >= from_date(d1) since m1 <= 12, dd1 <= dim
            lemma_from_date_day_offset(y1, 12, 31);
            if m1 < 12 {
                lemma_from_date_first_of_month_increasing(y1, m1, 12);
            }
            // from_date(Date(y1+1, 1, 1)) = from_date(Date(y1, 12, 1)) + 31 by month_step(y1, 12)
            lemma_from_date_month_step(y1, 12);
            assert(Date(y1, 12, 1).add_months(1) == Date(y1 + 1, 1, 1));
            // So from_date(Date(y1+1, 1, 1)) > from_date(Date(y1, 12, 31))
            // Now chain to (y2, m2, dd2)
            if y2 > y1 + 1 {
                // Induction through intermediate years
                lemma_from_date_cross_year_lower_bound(y1 + 1, y2);
            }
            // from_date(Date(y2, 1, 1)) <= from_date(Date(y2, m2, dd2))
            lemma_from_date_day_offset(y2, 1, 1);
            if m2 > 1 {
                lemma_from_date_first_of_month_increasing(y2, 1, m2);
            }
        }
    }

    // One year has >= 365 days.
    proof fn lemma_from_date_one_year_step(y: int)
        ensures EpochDelta::from_date(Date(y + 1, 1, 1)).delta()
             >= EpochDelta::from_date(Date(y, 1, 1)).delta() + 365,
    {
        let k = years_since_epoch(y + 1, 1); // = y - 2000
        lemma_leap_correction_step(k);
    }

    proof fn lemma_from_date_cross_year_lower_bound(y1: int, y2: int)
        requires y1 < y2,
        ensures EpochDelta::from_date(Date(y2, 1, 1)).delta()
             >= EpochDelta::from_date(Date(y1, 1, 1)).delta() + 365,
        decreases y2 - y1,
    {
        lemma_from_date_one_year_step(y1);
        if y2 > y1 + 1 {
            lemma_from_date_cross_year_lower_bound(y1 + 1, y2);
        }
    }

    // The other round-trip: to_ymd(from_date(d)) == d for valid dates.
    // Follows from the first round-trip + injectivity of from_date.
    pub proof fn theorem_epoch_delta_to_ymd_from_date_inverse(d: Date)
        requires d.is_valid(),
        ensures EpochDelta::to_ymd(EpochDelta::from_date(d)) == d,
    {
        let ed = EpochDelta::from_date(d);
        let d2 = ed.to_ymd();
        // from_date(to_ymd(ed)) == ed, so from_date(d2) == from_date(d)
        theorem_epoch_delta_from_date_to_ymd_inverse(ed);
        // d2 is valid since to_ymd always yields a valid date
        lemma_to_ymd_is_valid(ed);
        // d and d2 are both valid with from_date(d) == from_date(d2), so d == d2 by injectivity
        theorem_epoch_delta_congruent_preserves_comparison(d, ed, d2, EpochDelta::from_date(d2));
    }

    pub proof fn theorem_epoch_delta_congruent_preserves_comparison(d1: Date, ed1: EpochDelta, d2: Date, ed2: EpochDelta)
        requires d1.is_valid(), d2.is_valid(), ed_congruent(d1, ed1), ed_congruent(d2, ed2),
        ensures
            (d1.lt(d2) <==> ed1.lt(ed2)),
            (d1.eq(d2)  <==> ed1.eq(ed2)),
    {
        // ed1 == from_date(d1), ed2 == from_date(d2) by definition of congruent
        lemma_date_lt_is_total(d1, d2);
        if d1.lt(d2) {
            lemma_from_date_strict_monotone(d1, d2);
        }
        if d2.lt(d1) {
            lemma_from_date_strict_monotone(d2, d1);
        }
        // All four ensures clauses follow:
        // d1.lt(d2) ==> delta(d1) < delta(d2) ==> ed1.lt(ed2)          [strict mono]
        // ed1.lt(ed2) ==> delta(d1) < delta(d2) ==> !d2.lt(d1) && d1 != d2 ==> d1.lt(d2) [totality + contrapositive]
        // d1 == d2 ==> from_date(d1) == from_date(d2) ==> ed1 == ed2     [trivial]
        // ed1 == ed2 ==> delta equal ==> !d1.lt(d2) && !d2.lt(d1) ==> d1 == d2 [totality + contrapositive]
    }

    // Congruence is preserved under period addition.
    pub proof fn theorem_epoch_delta_add_period_preserves_congruence(d: Date, ed: EpochDelta, p: Period)
        requires d.is_valid(), ed_congruent(d, ed),
        ensures ed_congruent(d.add_period(p), ed.add_period(p)),
    {
        // ed == from_date(d) by definition of congruent.
        // Goal: from_date(d.add_period(p)) == ed.add_period(p).
        let n = p.years() * 12 + p.months();
        let days = p.days();

        // Step 1: d == ed.to_ymd() (the other round-trip)
        theorem_epoch_delta_to_ymd_from_date_inverse(d);
        assert(d == ed.to_ymd());

        // Step 2: d.add_months(n) is valid
        lemma_date_add_months_preserves_validity(d, n);

        // Step 3: from_date(d.add_months(n).add_days(days)).delta()
        //       == from_date(d.add_months(n)).delta() + days
        lemma_from_date_add_days(d.add_months(n), days);

        // Step 4: ed.add_period(p)
        //       = ed.add_months(n).add_days(days)
        //       = EpochDelta(from_date(ed.to_ymd().add_months(n)).delta() + days)
        //       = EpochDelta(from_date(d.add_months(n)).delta() + days)   [since d == ed.to_ymd()]
        //       = from_date(d.add_months(n).add_days(days))                [by step 3]
        //       = from_date(d.add_period(p))
    }

} // verus!
