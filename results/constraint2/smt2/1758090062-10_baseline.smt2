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
 (let (($x212 (<= x_day 28)))
 (let (($x415 (<= x_day 29)))
 (let (($x422 (= (mod x_year 400) 0)))
 (let (($x337 (= (mod x_year 4) 0)))
 (let (($x250 (ite (or (and $x337 (and (distinct (mod x_year 100) 0) true)) $x422) $x415 $x212)))
 (let (($x581 (= x_month 2)))
 (ite $x581 $x250 true))))))))
(assert
 (let (($x476 (<= x_day 30)))
 (let (($x280 (= x_month 4)))
 (let (($x481 (or $x280 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x481 $x476 true)))))
(assert
 (let (($x306 (= x_year 2023)))
 (let (($x570 (and $x306 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x570)))))
(assert
 (let (($x306 (= x_year 2023)))
(let (($x182 (and $x306 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x182)))))
(check-sat)
