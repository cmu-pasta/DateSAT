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
 (let (($x312 (<= x_day 28)))
 (let (($x371 (<= x_day 29)))
 (let (($x115 (= (mod x_year 400) 0)))
 (let (($x134 (= (mod x_year 4) 0)))
 (let (($x359 (ite (or (and $x134 (and (distinct (mod x_year 100) 0) true)) $x115) $x371 $x312)))
 (let (($x231 (= x_month 2)))
 (ite $x231 $x359 true))))))))
(assert
 (let (($x416 (<= x_day 30)))
 (let (($x369 (= x_month 4)))
 (let (($x370 (or $x369 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x370 $x416 true)))))
(assert
 (let (($x648 (= x_year 2023)))
 (let (($x430 (and $x648 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x430)))))
(assert
 (let (($x648 (= x_year 2023)))
(let (($x592 (and $x648 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x592)))))
(check-sat)
