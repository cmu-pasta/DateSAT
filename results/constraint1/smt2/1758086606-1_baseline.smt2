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
 (let (($x135 (<= x_day 28)))
 (let (($x133 (<= x_day 29)))
 (let (($x130 (= (mod x_year 400) 0)))
 (let (($x125 (= (mod x_year 4) 0)))
 (let (($x136 (ite (or (and $x125 (and (distinct (mod x_year 100) 0) true)) $x130) $x133 $x135)))
 (let (($x123 (= x_month 2)))
 (ite $x123 $x136 true))))))))
(assert
 (let (($x151 (<= x_day 30)))
 (let (($x149 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x149 $x151 true))))
(assert
 (let (($x156 (= x_year 2000)))
 (let (($x161 (and $x156 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x161))))
(assert
 (let (($x156 (= x_year 2000)))
 (let (($x176 (and $x156 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x176))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
