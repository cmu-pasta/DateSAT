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
 (let (($x644 (<= x_day 28)))
 (let (($x289 (<= x_day 29)))
 (let (($x316 (= (mod x_year 400) 0)))
 (let (($x507 (= (mod x_year 4) 0)))
 (let (($x617 (ite (or (and $x507 (and (distinct (mod x_year 100) 0) true)) $x316) $x289 $x644)))
 (let (($x525 (= x_month 2)))
 (ite $x525 $x617 true))))))))
(assert
 (let (($x151 (<= x_day 30)))
 (let (($x228 (= x_month 4)))
 (let (($x652 (or $x228 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x652 $x151 true)))))
(assert
 (let (($x605 (= x_year 2023)))
 (let (($x363 (and $x605 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x363)))))
(assert
 (let (($x605 (= x_year 2023)))
(let (($x510 (and $x605 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x510)))))
(check-sat)
