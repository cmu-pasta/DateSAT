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
 (let (($x492 (<= x_day 29)))
 (let (($x230 (= (mod x_year 400) 0)))
 (let (($x221 (= (mod x_year 4) 0)))
 (let (($x365 (ite (or (and $x221 (and (distinct (mod x_year 100) 0) true)) $x230) $x492 $x242)))
 (let (($x612 (= x_month 2)))
 (ite $x612 $x365 true))))))))
(assert
 (let (($x610 (<= x_day 30)))
 (let (($x621 (= x_month 4)))
 (let (($x234 (or $x621 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x234 $x610 true)))))
(assert
 (let (($x345 (= x_year 2023)))
 (let (($x538 (and $x345 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x538)))))
(assert
 (let (($x345 (= x_year 2023)))
(let (($x454 (and $x345 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x454)))))
(check-sat)
