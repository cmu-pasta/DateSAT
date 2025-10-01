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
 (let (($x462 (<= x_day 28)))
 (let (($x297 (<= x_day 29)))
 (let (($x688 (= (mod x_year 400) 0)))
 (let (($x215 (= (mod x_year 4) 0)))
 (let (($x247 (ite (or (and $x215 (and (distinct (mod x_year 100) 0) true)) $x688) $x297 $x462)))
 (let (($x233 (= x_month 2)))
 (ite $x233 $x247 true))))))))
(assert
 (let (($x250 (<= x_day 30)))
 (let (($x444 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x444 $x250 true))))
(assert
 (let (($x421 (= x_year 2022)))
 (let (($x424 (and $x421 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x424)))))
(assert
 (let (($x421 (= x_year 2022)))
(let (($x653 (and $x421 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x653)))))
(check-sat)
