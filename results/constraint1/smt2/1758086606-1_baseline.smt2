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
 (let (($x51 (<= x_day 28)))
 (let (($x49 (<= x_day 29)))
 (let (($x46 (= (mod x_year 400) 0)))
 (let (($x39 (= (mod x_year 4) 0)))
 (let (($x52 (ite (or (and $x39 (and (distinct (mod x_year 100) 0) true)) $x46) $x49 $x51)))
 (let (($x35 (= x_month 2)))
 (ite $x35 $x52 true))))))))
(assert
 (let (($x70 (<= x_day 30)))
 (let (($x68 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x68 $x70 true))))
(assert
 (let (($x76 (= x_year 2000)))
 (let (($x81 (and $x76 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x81))))
(assert
 (let (($x76 (= x_year 2000)))
 (let (($x97 (and $x76 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x97))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
