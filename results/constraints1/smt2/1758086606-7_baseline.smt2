; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_day () Int)
(declare-fun x_year () Int)
(assert
 (>= x_month 1))
(assert
 (<= x_month 12))
(assert
 (>= x_day 1))
(assert
 (<= x_day 31))
(assert
 (let (($x830 (<= x_day 28)))
 (let (($x203 (<= x_day 29)))
 (let (($x108 (= (mod x_year 400) 0)))
 (let (($x245 (= (mod x_year 4) 0)))
 (let (($x216 (ite (or (and $x245 (and (distinct (mod x_year 100) 0) true)) $x108) $x203 $x830)))
 (let (($x829 (= x_month 2)))
 (ite $x829 $x216 true))))))))
(assert
 (let (($x765 (<= x_day 30)))
 (let (($x618 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x618 $x765 true))))
(assert
 (let (($x837 (= x_year 2022)))
 (let (($x835 (and $x837 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x835)))))
(assert
 (let (($x837 (= x_year 2022)))
(let (($x676 (and $x837 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x676)))))
(check-sat)
