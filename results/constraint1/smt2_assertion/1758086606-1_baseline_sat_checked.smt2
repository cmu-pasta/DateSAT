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
 (let (($x238 (<= x_day 28)))
 (let (($x237 (<= x_day 29)))
 (let (($x229 (= (mod x_year 400) 0)))
 (let (($x555 (= (mod x_year 4) 0)))
 (let (($x330 (ite (or (and $x555 (and (distinct (mod x_year 100) 0) true)) $x229) $x237 $x238)))
 (let (($x549 (= x_month 2)))
 (ite $x549 $x330 true))))))))
(assert
 (let (($x212 (<= x_day 30)))
 (let (($x218 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x218 $x212 true))))
(assert
 (let (($x372 (= x_year 2000)))
 (let (($x388 (and $x372 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x388))))
(assert
 (let (($x372 (= x_year 2000)))
 (let (($x439 (and $x372 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x439))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(assert
 (let (($x464 (= x_day 29)))
(let (($x549 (= x_month 2)))
(let (($x372 (= x_year 2000)))
(and $x372 $x549 $x464)))))
(check-sat)
