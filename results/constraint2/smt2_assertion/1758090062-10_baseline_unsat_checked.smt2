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
 (let (($x1102 (<= x_day 28)))
 (let (($x342 (<= x_day 29)))
 (let (($x374 (= (mod x_year 400) 0)))
 (let (($x1119 (= (mod x_year 4) 0)))
 (let (($x1106 (ite (or (and $x1119 (and (distinct (mod x_year 100) 0) true)) $x374) $x342 $x1102)))
 (let (($x251 (= x_month 2)))
 (ite $x251 $x1106 true))))))))
(assert
 (let (($x443 (<= x_day 30)))
 (let (($x255 (= x_month 4)))
 (let (($x451 (or $x255 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x451 $x443 true)))))
(assert
 (let (($x1101 (= x_year 2023)))
 (let (($x1470 (and $x1101 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x1470)))))
(assert
 (let (($x1101 (= x_year 2023)))
(let (($x1574 (and $x1101 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x1574)))))
(check-sat)
