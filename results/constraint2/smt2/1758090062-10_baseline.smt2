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
 (let (($x464 (<= x_day 28)))
 (let (($x582 (<= x_day 29)))
 (let (($x332 (= (mod x_year 400) 0)))
 (let (($x513 (= (mod x_year 4) 0)))
 (let (($x451 (ite (or (and $x513 (and (distinct (mod x_year 100) 0) true)) $x332) $x582 $x464)))
 (let (($x515 (= x_month 2)))
 (ite $x515 $x451 true))))))))
(assert
 (let (($x665 (<= x_day 30)))
 (let (($x593 (= x_month 4)))
 (let (($x667 (or $x593 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x667 $x665 true)))))
(assert
 (let (($x744 (= x_year 2023)))
 (let (($x675 (and $x744 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x675)))))
(assert
 (let (($x744 (= x_year 2023)))
(let (($x763 (and $x744 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x763)))))
(check-sat)
