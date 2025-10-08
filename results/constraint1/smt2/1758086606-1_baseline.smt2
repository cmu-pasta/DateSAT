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
 (let (($x239 (<= x_day 28)))
 (let (($x238 (<= x_day 29)))
 (let (($x236 (= (mod x_year 400) 0)))
 (let (($x229 (= (mod x_year 4) 0)))
 (let (($x240 (ite (or (and $x229 (and (distinct (mod x_year 100) 0) true)) $x236) $x238 $x239)))
 (let (($x227 (= x_month 2)))
 (ite $x227 $x240 true))))))))
(assert
 (let (($x254 (<= x_day 30)))
 (let (($x253 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x253 $x254 true))))
(assert
 (let (($x260 (= x_year 2000)))
 (let (($x265 (and $x260 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x265))))
(assert
 (let (($x260 (= x_year 2000)))
 (let (($x280 (and $x260 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x280))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
