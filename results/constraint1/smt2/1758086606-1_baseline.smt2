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
 (let (($x242 (<= x_day 28)))
 (let (($x241 (<= x_day 29)))
 (let (($x239 (= (mod x_year 400) 0)))
 (let (($x232 (= (mod x_year 4) 0)))
 (let (($x243 (ite (or (and $x232 (and (distinct (mod x_year 100) 0) true)) $x239) $x241 $x242)))
 (let (($x230 (= x_month 2)))
 (ite $x230 $x243 true))))))))
(assert
 (let (($x257 (<= x_day 30)))
 (let (($x256 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x256 $x257 true))))
(assert
 (let (($x262 (= x_year 2000)))
 (let (($x267 (and $x262 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x267))))
(assert
 (let (($x262 (= x_year 2000)))
 (let (($x282 (and $x262 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x282))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
