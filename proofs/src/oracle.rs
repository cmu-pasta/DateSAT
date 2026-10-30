use vstd::prelude::*;
use vstd::math::*;
use vstd::arithmetic::div_mod::lemma_fundamental_div_mod_converse;
use crate::*;

// Executable counterparts of the reference spec functions, used as a test oracle
// (see tests/spec_adequacy/). Each one is proved to agree with its spec function
// whenever it returns Some; it returns None only when a machine-integer operation
// would overflow, so there are no overflow proofs. That the oracle returns Some on
// every tested input is checked by the tests, not proved.

verus! {

    /// An executable SimpleDate.
    pub struct XDate {
        pub y: i64,
        pub m: i64,
        pub d: i64,
    }

    impl XDate {
        pub open spec fn view(self) -> SimpleDate {
            SimpleDate(self.y as int, self.m as int, self.d as int)
        }
    }

    /// Euclidean division by a positive divisor, matching Verus's `int` `/` and `%`.
    /// The candidate is checked against its certificate x == q * d + r, 0 <= r < d.
    pub fn x_ediv(x: i64, d: i64) -> (res: Option<(i64, i64)>)
        requires d > 0,
        ensures res matches Some((q, r)) ==> q as int == x as int / d as int && r as int == x as int % d as int,
    {
        let mut q = x / d;
        let mut r = x % d;
        if r < 0 {
            q = q.checked_sub(1)?;
            r = r.checked_add(d)?;
        }
        let s = q.checked_mul(d)?.checked_add(r)?;
        if s != x || r < 0 || r >= d {
            return None;
        }
        proof { lemma_fundamental_div_mod_converse(x as int, d as int, q as int, r as int); }
        Some((q, r))
    }

    pub fn x_leap(y: i64) -> (res: Option<bool>)
        ensures res matches Some(b) ==> b == leap(y as int),
    {
        let (_, r4) = x_ediv(y, 4)?;
        let (_, r100) = x_ediv(y, 100)?;
        let (_, r400) = x_ediv(y, 400)?;
        Some(r4 == 0 && (r100 != 0 || r400 == 0))
    }

    pub fn x_dim(y: i64, m: i64) -> (res: Option<i64>)
        requires 1 <= m <= 12,
        ensures res matches Some(v) ==> v as int == dim(y as int, m as int),
    {
        let lp = x_leap(y)?;
        Some(if m == 2 {
            if lp { 29 } else { 28 }
        } else if m == 4 || m == 6 || m == 9 || m == 11 {
            30
        } else {
            31
        })
    }

    pub fn x_is_valid(x: XDate) -> (res: Option<bool>)
        ensures res matches Some(b) ==> b == x@.is_valid(),
    {
        if !(1 <= x.m && x.m <= 12) {
            return Some(false);
        }
        let dm = x_dim(x.y, x.m)?;
        Some(1 <= x.d && x.d <= dm)
    }

    pub fn x_lt(a: XDate, b: XDate) -> (res: bool)
        ensures res == a@.lt(b@),
    {
        a.y < b.y || (a.y == b.y && a.m < b.m) || (a.y == b.y && a.m == b.m && a.d < b.d)
    }

    pub fn x_add_months(x: XDate, n: i64) -> (res: Option<XDate>)
        ensures res matches Some(v) ==> v@ == x@.add_months(n as int) && 1 <= v.m <= 12,
    {
        let t = x.m.checked_sub(1)?.checked_add(n)?;
        let (q, r) = x_ediv(t, 12)?;
        let y2 = x.y.checked_add(q)?;
        let m2 = r + 1;
        let dm = x_dim(y2, m2)?;
        let d2 = if x.d <= dm { x.d } else { dm };
        Some(XDate { y: y2, m: m2, d: d2 })
    }

    /// One rule of the recursive spec per loop iteration (ADD-DAYS, ADD-DAYS-OVER,
    /// ADD-DAYS-UNDER1, ADD-DAYS-UNDER2), so the loop invariant is a single unfolding.
    pub fn x_add_days(x: XDate, n: i64) -> (res: Option<XDate>)
        requires 1 <= x.m <= 12,
        ensures res matches Some(v) ==> v@ == x@.add_days(n as int),
    {
        let mut cur = x;
        let mut k = n;
        loop
            invariant
                1 <= cur.m <= 12,
                cur@.add_days(k as int) == x@.add_days(n as int),
            decreases (k < 0) as nat, abs(k as int),
        {
            let dm = x_dim(cur.y, cur.m)?;
            if !(1 <= cur.d && cur.d <= dm) {
                return Some(XDate { y: 0, m: 0, d: 0 });
            }
            let dk = cur.d.checked_add(k)?;
            if 1 <= dk && dk <= dm {
                return Some(XDate { y: cur.y, m: cur.m, d: dk });
            } else if dk > dm {
                let next = x_add_months(XDate { y: cur.y, m: cur.m, d: 1 }, 1)?;
                k = k - (dm - cur.d) - 1;
                cur = next;
            } else if cur.d > 1 {
                k = dk - 1;
                cur = XDate { y: cur.y, m: cur.m, d: 1 };
            } else {
                let prev = x_add_months(cur, -1)?;
                let dmp = x_dim(prev.y, prev.m)?;
                proof { lemma_dim_is_bounded(prev.y as int, prev.m as int); }
                k = k + dmp;
                cur = XDate { y: prev.y, m: prev.m, d: 1 };
            }
        }
    }

    pub fn x_add_period(x: XDate, years: i64, months: i64, days: i64) -> (res: Option<XDate>)
        ensures res matches Some(v) ==> v@ == x@.add_period(Period(years as int, months as int, days as int)),
    {
        let n = years.checked_mul(12)?.checked_add(months)?;
        let mid = x_add_months(x, n)?;
        x_add_days(mid, days)
    }

    pub fn x_from_simple_date(x: XDate) -> (res: Option<i64>)
        ensures res matches Some(v) ==> v as int == EpochDelta::from_simple_date(x@).delta(),
    {
        let ye = (if x.m <= 2 { x.y.checked_sub(1)? } else { x.y }).checked_sub(2000)?;
        let (q4, _) = x_ediv(ye, 4)?;
        let (q100, _) = x_ediv(ye, 100)?;
        let (q400, _) = x_ediv(ye, 400)?;
        let by_years = ye.checked_mul(365)?.checked_add(q4)?.checked_sub(q100)?.checked_add(q400)?;
        let me = if x.m <= 2 { x.m.checked_add(9)? } else { x.m.checked_sub(3)? };
        let (by_months, _) = x_ediv(me.checked_mul(153)?.checked_add(2)?, 5)?;
        let by_dim = x.d.checked_sub(1)?;
        Some(by_years.checked_add(by_months)?.checked_add(by_dim)?)
    }

    pub fn x_epoch_to_ymd(delta: i64) -> (res: Option<XDate>)
        ensures res matches Some(v) ==> v@ == EpochDelta(delta as int).to_ymd(),
    {
        x_add_days(XDate { y: 2000, m: 3, d: 1 }, delta)
    }

    pub fn x_year_of_alpha(alpha: i64) -> (res: Option<i64>)
        ensures res matches Some(v) ==> v as int == year_of_alpha(alpha as int),
    {
        let (q, _) = x_ediv(alpha.checked_add(2000 * 12 + 2)?, 12)?;
        Some(q)
    }

    pub fn x_month_of_alpha(alpha: i64) -> (res: Option<i64>)
        ensures res matches Some(v) ==> v as int == month_of_alpha(alpha as int),
    {
        let (_, r) = x_ediv(alpha.checked_add(2000 * 12 + 2)?, 12)?;
        Some(r + 1)
    }

    pub fn x_ab_from_simple_date(x: XDate) -> (res: Option<(i64, i64)>)
        ensures res matches Some((a, b)) ==> a as int == AlphaBeta::from_simple_date(x@).alpha()
                                            && b as int == AlphaBeta::from_simple_date(x@).beta(),
    {
        let ye = (if x.m <= 2 { x.y.checked_sub(1)? } else { x.y }).checked_sub(2000)?;
        let me = if x.m <= 2 { x.m.checked_add(9)? } else { x.m.checked_sub(3)? };
        Some((ye.checked_mul(12)?.checked_add(me)?, x.d.checked_sub(1)?))
    }

    #[verifier::external_body]
    pub fn run() {
        driver::run()
    }

} // verus!

/// Line-oriented driver for the compiled oracle. Not verified: it only parses
/// integers, calls the functions above, and prints their results. Each input line
/// is `op arg...`; each output line is the result, or `none` when the oracle
/// returned None.
mod driver {
    use super::*;
    use std::io::{BufRead, BufWriter, Write};

    fn date(v: &[i64]) -> XDate {
        XDate { y: v[0], m: v[1], d: v[2] }
    }

    fn show_date(r: Option<XDate>) -> String {
        r.map_or("none".to_string(), |x| format!("{} {} {}", x.y, x.m, x.d))
    }

    fn show<T: std::fmt::Display>(r: Option<T>) -> String {
        r.map_or("none".to_string(), |x| x.to_string())
    }

    fn eval(line: &str) -> String {
        let mut parts = line.split_whitespace();
        let op = parts.next().unwrap_or("");
        let v: Vec<i64> = parts.map(|s| s.parse().expect("integer argument")).collect();
        match op {
            "leap" => show(x_leap(v[0])),
            "dim" if (1..=12).contains(&v[1]) => show(x_dim(v[0], v[1])),
            "valid" => show(x_is_valid(date(&v))),
            "lt" => x_lt(date(&v[0..3]), date(&v[3..6])).to_string(),
            "add_months" => show_date(x_add_months(date(&v), v[3])),
            "add_days" if (1..=12).contains(&v[1]) => show_date(x_add_days(date(&v), v[3])),
            "add_period" => show_date(x_add_period(date(&v), v[3], v[4], v[5])),
            "from_simple_date" => show(x_from_simple_date(date(&v))),
            "epoch_to_ymd" => show_date(x_epoch_to_ymd(v[0])),
            "year_of_alpha" => show(x_year_of_alpha(v[0])),
            "month_of_alpha" => show(x_month_of_alpha(v[0])),
            "ab_from_simple_date" => {
                x_ab_from_simple_date(date(&v)).map_or("none".to_string(), |(a, b)| format!("{} {}", a, b))
            }
            _ => panic!("unknown or out-of-domain request: {}", line),
        }
    }

    pub fn run() {
        let stdin = std::io::stdin();
        let mut out = BufWriter::new(std::io::stdout().lock());
        for line in stdin.lock().lines() {
            let line = line.expect("read stdin");
            if !line.trim().is_empty() {
                writeln!(out, "{}", eval(&line)).expect("write stdout");
            }
        }
    }
}
