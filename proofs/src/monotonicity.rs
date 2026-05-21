use vstd::prelude::*;
use vstd::math::*;
use crate::*;

verus! {

    // --- Monotonicity helpers and lemmas ---

    proof fn lemma_min_leq_compat(a: int, b: int, c: int)
        requires a <= b,
        ensures min(a, c) <= min(b, c)
    {
        // QED
    }

    proof fn lemma_euclid_div_mod_order(a: int, b: int, k: int) by(nonlinear_arith)
        requires a < b, k > 0,
        ensures a / k < b / k || (a / k == b / k && a % k < b % k)
    {
    }

    pub proof fn lemma_add_months_is_monotonic(d1: SimpleDate, d2: SimpleDate, n: int)
        requires d1.is_valid() && d2.is_valid() && d1.leq(d2),
        ensures d1.add_months(n).leq(d2.add_months(n))
    {
        if d1 == d2 {
            lemma_date_leq_is_reflexive(d1.add_months(n));
            return;
        }
        let SimpleDate(y1, m1, day1) = d1;
        let SimpleDate(y2, m2, day2) = d2;
        let mi1 = m1 - 1 + n;
        let mi2 = m2 - 1 + n;
        let y1_ = y1 + mi1 / 12;
        let m1_ = 1 + (mi1 % 12);
        let y2_ = y2 + mi2 / 12;
        let m2_ = 1 + (mi2 % 12);

        if y1 < y2 {
            // Case A: year differs
            if y1_ < y2_ {
                // lt by year, done
            } else if y1_ == y2_ {
                assert(mi1/12 == mi2/12 + 1);
                assert(mi1 - mi2 == m1 - m2);
                assert(mi1 == (mi1/12)*12 + mi1%12);
                assert(mi2 == (mi2/12)*12 + mi2%12);
                assert(mi1%12 - mi2%12 == m1 - m2 - 12);
                assert(mi1 % 12 < mi2 % 12);
                assert(m1_ < m2_);
            } else {
                assert(mi1 - mi2 == m1 - m2);
                assert(-11 <= mi1 - mi2 <= 11);
                assert(false) by(nonlinear_arith)
                    requires y1_ > y2_,
                             y1_ == y1 + mi1 / 12,
                             y2_ == y2 + mi2 / 12,
                             y1 < y2,
                             -11 <= mi1 - mi2 <= 11;
            }
        } else if y1 == y2 && m1 < m2 {
            // Case B: same year, month differs
            assert(mi1 < mi2);
            lemma_euclid_div_mod_order(mi1, mi2, 12);
            if mi1 / 12 < mi2 / 12 {
                assert(y1_ < y2_);
            } else {
                assert(mi1 / 12 == mi2 / 12 && mi1 % 12 < mi2 % 12);
                assert(y1_ == y2_);
                assert(m1_ < m2_);
            }
        } else {
            // Case C: same year, same month, day differs
            assert(y1 == y2 && m1 == m2 && day1 < day2);
            assert(mi1 == mi2);
            assert(y1_ == y2_ && m1_ == m2_);
            lemma_min_leq_compat(day1, day2, dim(y1_, m1_));
        }
    }

    // Helper: the first day of the next month is after any day in the current month
    proof fn lemma_first_of_next_month_is_after(y: int, m: int, d: int)
        requires 1 <= m <= 12, 1 <= d <= dim(y, m),
        ensures SimpleDate(y, m, d).lt(SimpleDate(y, m, 1).add_months(1))
    {
    }

    // Helper: add_days with n >= 0 on a valid date produces a result >= the date
    proof fn lemma_add_days_pos_is_geq(d: SimpleDate, n: int)
        requires d.is_valid(), n >= 0,
        ensures d.leq(d.add_days(n)),
        decreases n
    {
        let SimpleDate(y, m, dd) = d;
        if 1 <= dd + n <= dim(y, m) {
        } else {
            assert(dd + n > dim(y, m));
            let d_ = SimpleDate(y, m, 1).add_months(1);
            let n_ = n - (dim(y, m) - dd) - 1;
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), 1);
            lemma_first_of_next_month_is_after(y, m, dd);
            lemma_add_days_pos_is_geq(d_, n_);
            lemma_date_leq_is_transitive(d, d_, d_.add_days(n_));
        }
    }

    proof fn lemma_add_days_pos_monotonic_in_n(d: SimpleDate, n1: int, n2: int)
        requires d.is_valid(), 0 <= n1 <= n2,
        ensures d.add_days(n1).leq(d.add_days(n2)),
        decreases n2
    {
        let SimpleDate(y, m, dd) = d;
        if n1 == n2 {
            lemma_date_leq_is_reflexive(d.add_days(n1));
        } else if 1 <= dd + n2 <= dim(y, m) {
        } else if 1 <= dd + n1 <= dim(y, m) {
            let d_ = SimpleDate(y, m, 1).add_months(1);
            let n2_ = n2 - (dim(y, m) - dd) - 1;
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), 1);
            lemma_first_of_next_month_is_after(y, m, dd + n1);
            lemma_add_days_pos_is_geq(d_, n2_);
            lemma_date_lt_implies_leq(SimpleDate(y, m, dd + n1), d_);
            lemma_date_leq_is_transitive(SimpleDate(y, m, dd + n1), d_, d_.add_days(n2_));
        } else {
            let d_ = SimpleDate(y, m, 1).add_months(1);
            let n1_ = n1 - (dim(y, m) - dd) - 1;
            let n2_ = n2 - (dim(y, m) - dd) - 1;
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), 1);
            lemma_add_days_pos_monotonic_in_n(d_, n1_, n2_);
        }
    }

    // Helper: last day of previous month is before any day in current month
    proof fn lemma_last_of_prev_month_is_before(y: int, m: int, d: int)
        requires 1 <= m <= 12, 1 <= d <= dim(y, m),
        ensures ({
            let SimpleDate(y_, m_, _) = SimpleDate(y, m, 1).add_months(-1);
            SimpleDate(y_, m_, dim(y_, m_)).lt(SimpleDate(y, m, d))
        })
    {
    }

    // Helper: add_days with n <= 0 on a valid date produces a result <= the date
    proof fn lemma_add_days_neg_is_leq(d: SimpleDate, n: int)
        requires d.is_valid(), n <= 0,
        ensures d.add_days(n).leq(d),
        decreases abs(n)
    {
        let SimpleDate(y, m, dd) = d;
        if 1 <= dd + n {
        } else if dd > 1 {
            let n_ = dd - 1 + n;
            lemma_add_days_neg_is_leq(SimpleDate(y, m, 1), n_);
            lemma_date_leq_is_transitive(SimpleDate(y, m, 1).add_days(n_), SimpleDate(y, m, 1), d);
        } else {
            let SimpleDate(y_, m_, _) = d.add_months(-1);
            let n_ = n + dim(y_, m_);
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), -1);
            if n_ >= 0 {
                lemma_add_days_pos_is_geq(SimpleDate(y_, m_, 1), n_);
                lemma_last_of_prev_month_is_before(y, m, dd);
                lemma_dim_is_bounded(y_, m_);
                lemma_add_days_pos_monotonic_in_n(SimpleDate(y_, m_, 1), n_, dim(y_, m_) - 1);
                lemma_date_lt_implies_leq(SimpleDate(y_, m_, dim(y_, m_)), d);
                lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1).add_days(n_), SimpleDate(y_, m_, dim(y_, m_)), d);
            } else {
                lemma_add_days_neg_is_leq(SimpleDate(y_, m_, 1), n_);
                lemma_last_of_prev_month_is_before(y, m, dd);
                lemma_date_lt_implies_leq(SimpleDate(y_, m_, 1), SimpleDate(y_, m_, dim(y_, m_)));
                lemma_date_lt_implies_leq(SimpleDate(y_, m_, dim(y_, m_)), d);
                lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1), SimpleDate(y_, m_, dim(y_, m_)), d);
                lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1).add_days(n_), SimpleDate(y_, m_, 1), d);
            }
        }
    }

    proof fn lemma_add_days_neg_monotonic_in_n(d: SimpleDate, n1: int, n2: int)
        requires d.is_valid(), n1 <= n2 <= 0,
        ensures d.add_days(n1).leq(d.add_days(n2)),
        decreases abs(n1)
    {
        let SimpleDate(y, m, dd) = d;
        if n1 == n2 {
            lemma_date_leq_is_reflexive(d.add_days(n1));
        } else if 1 <= dd + n1 {
        } else if 1 <= dd + n2 {
            lemma_add_days_neg_is_leq(d, n1);
            if dd > 1 {
                lemma_add_days_neg_is_leq(SimpleDate(y, m, 1), dd - 1 + n1);
                lemma_date_leq_is_transitive(SimpleDate(y, m, 1).add_days(dd - 1 + n1), SimpleDate(y, m, 1), SimpleDate(y, m, dd + n2));
            } else {
                let SimpleDate(y_, m_, _) = d.add_months(-1);
                let n1_ = n1 + dim(y_, m_);
                lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), -1);
                if n1_ >= 0 {
                    lemma_add_days_pos_is_geq(SimpleDate(y_, m_, 1), n1_);
                    lemma_dim_is_bounded(y_, m_);
                    lemma_add_days_pos_monotonic_in_n(SimpleDate(y_, m_, 1), n1_, dim(y_, m_) - 1);
                    lemma_last_of_prev_month_is_before(y, m, dd + n2);
                    lemma_date_lt_implies_leq(SimpleDate(y_, m_, dim(y_, m_)), SimpleDate(y, m, dd + n2));
                    lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1).add_days(n1_), SimpleDate(y_, m_, dim(y_, m_)), SimpleDate(y, m, dd + n2));
                } else {
                    lemma_add_days_neg_is_leq(SimpleDate(y_, m_, 1), n1_);
                    lemma_last_of_prev_month_is_before(y, m, dd + n2);
                    lemma_date_lt_implies_leq(SimpleDate(y_, m_, 1), SimpleDate(y_, m_, dim(y_, m_)));
                    lemma_date_lt_implies_leq(SimpleDate(y_, m_, dim(y_, m_)), SimpleDate(y, m, dd + n2));
                    lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1), SimpleDate(y_, m_, dim(y_, m_)), SimpleDate(y, m, dd + n2));
                    lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1).add_days(n1_), SimpleDate(y_, m_, 1), SimpleDate(y, m, dd + n2));
                }
            }
        } else if dd > 1 {
            let n1_ = dd - 1 + n1;
            let n2_ = dd - 1 + n2;
            lemma_add_days_neg_monotonic_in_n(SimpleDate(y, m, 1), n1_, n2_);
        } else {
            let SimpleDate(y_, m_, _) = d.add_months(-1);
            let n1_ = n1 + dim(y_, m_);
            let n2_ = n2 + dim(y_, m_);
            lemma_date_add_months_preserves_validity(SimpleDate(y, m, 1), -1);
            if n1_ >= 0 && n2_ >= 0 {
                lemma_add_days_pos_monotonic_in_n(SimpleDate(y_, m_, 1), n1_, n2_);
            } else if n1_ < 0 && n2_ >= 0 {
                lemma_add_days_neg_is_leq(SimpleDate(y_, m_, 1), n1_);
                lemma_add_days_pos_is_geq(SimpleDate(y_, m_, 1), n2_);
                lemma_date_leq_is_transitive(SimpleDate(y_, m_, 1).add_days(n1_), SimpleDate(y_, m_, 1), SimpleDate(y_, m_, 1).add_days(n2_));
            } else {
                lemma_add_days_neg_monotonic_in_n(SimpleDate(y_, m_, 1), n1_, n2_);
            }
        }
    }

    // General monotonicity of add_days in n
    proof fn lemma_add_days_monotonic_in_n(d: SimpleDate, n1: int, n2: int)
        requires d.is_valid(), n1 <= n2,
        ensures d.add_days(n1).leq(d.add_days(n2))
    {
        if n1 >= 0 {
            lemma_add_days_pos_monotonic_in_n(d, n1, n2);
        } else if n2 <= 0 {
            lemma_add_days_neg_monotonic_in_n(d, n1, n2);
        } else {
            lemma_add_days_neg_is_leq(d, n1);
            lemma_add_days_pos_is_geq(d, n2);
            lemma_date_leq_is_transitive(d.add_days(n1), d, d.add_days(n2));
        }
    }

    // Step decomposition: d.add_days(n) == d.add_days(1).add_days(n-1) for n > 0
    proof fn lemma_add_days_step_forward(d: SimpleDate, n: int)
        requires d.is_valid(), n > 0,
        ensures d.add_days(n) == d.add_days(1).add_days(n - 1)
    {
        let SimpleDate(y, m, dd) = d;
        let dim = dim(y, m);
        if dd + 1 <= dim {
            assert(d.add_days(1) == SimpleDate(y, m, dd + 1));
            if dd + n <= dim {
                assert(d.add_days(n) == SimpleDate(y, m, dd + n));
                assert(SimpleDate(y, m, dd + 1).add_days(n - 1) == SimpleDate(y, m, dd + n));
            } else {
                assert(dd + n > dim);
                assert((dd + 1) + (n - 1) > dim);
                assert(n - (dim - dd) - 1 == (n - 1) - (dim - (dd + 1)) - 1);
            }
        } else {
            assert(dd == dim);
            assert(dd + n > dim);
            let d_next = SimpleDate(y, m, 1).add_months(1);
            assert(d.add_days(1) == d_next.add_days(0));
            assert(d.add_days(n) == d_next.add_days(n - 1));
        }
    }

    // Step decomposition: d.add_days(n) == d.add_days(-1).add_days(n+1) for n < 0
    proof fn lemma_add_days_step_backward(d: SimpleDate, n: int)
        requires d.is_valid(), n < 0,
        ensures d.add_days(n) == d.add_days(-1).add_days(n + 1)
    {
        let SimpleDate(y, m, dd) = d;
        if dd > 1 {
            assert(d.add_days(-1) == SimpleDate(y, m, dd - 1));
            if dd + n >= 1 {
                assert(d.add_days(n) == SimpleDate(y, m, dd + n));
                assert((dd - 1) + (n + 1) == dd + n);
                assert(SimpleDate(y, m, dd - 1).add_days(n + 1) == SimpleDate(y, m, dd + n));
            } else {
                assert(d.add_days(n) == SimpleDate(y, m, 1).add_days(dd - 1 + n));
                assert((dd - 1) + (n + 1) < 1);
                if dd - 1 > 1 {
                    assert(SimpleDate(y, m, dd - 1).add_days(n + 1) == SimpleDate(y, m, 1).add_days((dd - 2) + (n + 1)));
                    assert((dd - 2) + (n + 1) == dd - 1 + n);
                } else {
                    assert(dd == 2);
                    assert(dd - 1 + n == n + 1);
                }
            }
        } else {
            assert(dd == 1);
            let SimpleDate(y_, m_, _) = d.add_months(-1);
            let dim_ = dim(y_, m_);
            lemma_dim_is_bounded(y_, m_);
            assert(d.add_days(-1) == SimpleDate(y_, m_, 1).add_days(dim_ - 1));
            assert(1 <= dim_ - 1);
            assert(dim_ - 1 <= dim_);
            assert(SimpleDate(y_, m_, 1).add_days(dim_ - 1) == SimpleDate(y_, m_, dim_));
            assert(d.add_days(n) == SimpleDate(y_, m_, 1).add_days(n + dim_));
            if dim_ + (n + 1) >= 1 {
                assert(SimpleDate(y_, m_, dim_).add_days(n + 1) == SimpleDate(y_, m_, dim_ + n + 1));
                assert(SimpleDate(y_, m_, 1).add_days(n + dim_) == SimpleDate(y_, m_, 1 + n + dim_));
                assert(dim_ + n + 1 == 1 + n + dim_);
            } else {
                assert(dim_ + (n + 1) < 1);
                assert(SimpleDate(y_, m_, dim_).add_days(n + 1) == SimpleDate(y_, m_, 1).add_days(dim_ - 1 + (n + 1)));
                assert(dim_ - 1 + (n + 1) == n + dim_);
            }
        }
    }

    // One step forward: d1.lt(d2) ==> d1.add_days(1).leq(d2)
    proof fn lemma_one_step_forward(d1: SimpleDate, d2: SimpleDate)
        requires d1.is_valid() && d2.is_valid() && d1.lt(d2),
        ensures d1.add_days(1).leq(d2)
    {
        let SimpleDate(y1, m1, dd1) = d1;
        let SimpleDate(y2, m2, dd2) = d2;
        if y1 == y2 && m1 == m2 {
            assert(dd1 < dd2);
            assert(dd1 + 1 <= dd2);
            assert(dd1 + 1 <= dim(y1, m1));
            assert(d1.add_days(1) == SimpleDate(y1, m1, dd1 + 1));
        } else {
            if dd1 + 1 <= dim(y1, m1) {
                assert(d1.add_days(1) == SimpleDate(y1, m1, dd1 + 1));
            } else {
                assert(dd1 + 1 > dim(y1, m1));
                let d_next = SimpleDate(y1, m1, 1).add_months(1);
                assert(d1.add_days(1) == d_next.add_days(0));
                let mi = m1;
                let y_next = y1 + mi / 12;
                let m_next = 1 + (mi % 12);
                assert(d_next == SimpleDate(y_next, m_next, min(1, dim(y_next, m_next))));
                lemma_dim_is_bounded(y_next, m_next);
                assert(d_next == SimpleDate(y_next, m_next, 1));
                lemma_euclid_div_mod_order(m1 - 1, m2 - 1 + (y2 - y1) * 12, 12);
                if y_next < y2 || (y_next == y2 && m_next < m2) {
                    lemma_date_lt_implies_leq(d_next, d2);
                } else {
                    assert(y_next == y2 && m_next == m2);
                    assert(d_next == SimpleDate(y2, m2, 1));
                }
            }
        }
    }

    // One step backward: d1.lt(d2) ==> d1.leq(d2.add_days(-1))
    proof fn lemma_one_step_backward(d1: SimpleDate, d2: SimpleDate)
        requires d1.is_valid() && d2.is_valid() && d1.lt(d2),
        ensures d1.leq(d2.add_days(-1))
    {
        let SimpleDate(y1, m1, dd1) = d1;
        let SimpleDate(y2, m2, dd2) = d2;
        if y1 == y2 && m1 == m2 {
            assert(dd1 < dd2);
            assert(dd2 >= 2);
            assert(dd2 - 1 >= 1);
            assert(d2.add_days(-1) == SimpleDate(y2, m2, dd2 - 1));
        } else {
            if dd2 > 1 {
                assert(d2.add_days(-1) == SimpleDate(y2, m2, dd2 - 1));
                lemma_date_lt_implies_leq(d1, d2.add_days(-1));
            } else {
                assert(dd2 == 1);
                let SimpleDate(y2_, m2_, _) = d2.add_months(-1);
                let dim_ = dim(y2_, m2_);
                lemma_dim_is_bounded(y2_, m2_);
                assert(d2.add_days(-1) == SimpleDate(y2_, m2_, 1).add_days(dim_ - 1));
                assert(SimpleDate(y2_, m2_, 1).add_days(dim_ - 1) == SimpleDate(y2_, m2_, dim_));
                let mi = m2 - 2;
                assert(y2_ == y2 + mi / 12);
                assert(m2_ == 1 + (mi % 12));
                if y1 < y2_ || (y1 == y2_ && m1 < m2_) {
                    lemma_date_lt_implies_leq(d1, SimpleDate(y2_, m2_, dim_));
                } else {
                    assert(y1 == y2_ && m1 == m2_);
                }
            }
        }
    }

    // Monotonicity of add_days in the date argument
    pub proof fn lemma_add_days_is_monotonic(d1: SimpleDate, d2: SimpleDate, n: int)
        requires d1.is_valid() && d2.is_valid() && d1.leq(d2),
        ensures d1.add_days(n).leq(d2.add_days(n)),
        decreases abs(n)
    {
        if d1 == d2 {
            lemma_date_leq_is_reflexive(d1.add_days(n));
        } else if n == 0 {
            lemma_date_lt_implies_leq(d1, d2);
        } else if n > 0 {
            lemma_add_days_step_forward(d1, n);
            lemma_one_step_forward(d1, d2);
            lemma_date_add_days_preserves_validity(d1, 1);
            lemma_add_days_is_monotonic(d1.add_days(1), d2, n - 1);
            lemma_add_days_monotonic_in_n(d2, n - 1, n);
            lemma_date_leq_is_transitive(d1.add_days(n), d2.add_days(n - 1), d2.add_days(n));
        } else {
            lemma_add_days_step_backward(d2, n);
            lemma_one_step_backward(d1, d2);
            lemma_date_add_days_preserves_validity(d2, -1);
            lemma_add_days_is_monotonic(d1, d2.add_days(-1), n + 1);
            lemma_add_days_monotonic_in_n(d1, n, n + 1);
            lemma_date_leq_is_transitive(d1.add_days(n), d1.add_days(n + 1), d2.add_days(n));
        }
    }

    // Monotonicity of SimpleDate-Period Addition
    pub proof fn theorem_date_add_period_is_monotonic(d1: SimpleDate, d2: SimpleDate, p: Period)
        requires d1.is_valid() && d2.is_valid() && d1.leq(d2),
        ensures d1.add_period(p).leq(d2.add_period(p))
    {
        let m = p.years() * 12 + p.months();
        // Step 1: add_months is monotonic
        lemma_add_months_is_monotonic(d1, d2, m);

        // Step 2: both intermediate dates are valid
        lemma_date_add_months_preserves_validity(d1, m);
        lemma_date_add_months_preserves_validity(d2, m);

        // Step 3: add_days is monotonic in the date argument
        lemma_add_days_is_monotonic(d1.add_months(m), d2.add_months(m), p.days());
    }

} // verus!
