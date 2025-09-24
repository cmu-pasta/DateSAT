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
 (let (($x251 (<= x_day 28)))
 (let (($x585 (<= x_day 29)))
 (let (($x484 (= (mod x_year 400) 0)))
 (let (($x506 (= (mod x_year 4) 0)))
 (let (($x249 (ite (or (and $x506 (and (distinct (mod x_year 100) 0) true)) $x484) $x585 $x251)))
 (let (($x436 (= x_month 2)))
 (ite $x436 $x249 true))))))))
(assert
 (let (($x681 (<= x_day 30)))
 (let (($x370 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x370 $x681 true))))
(assert
 (let (($x575 (= x_year 2022)))
 (let (($x741 (and $x575 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x741)))))
(assert
 (let (($x575 (= x_year 2022)))
(let (($x229 (and $x575 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x229)))))
(check-sat)
