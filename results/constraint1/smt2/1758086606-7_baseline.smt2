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
 (let (($x627 (<= x_day 28)))
 (let (($x571 (<= x_day 29)))
 (let (($x235 (= (mod x_year 400) 0)))
 (let (($x786 (= (mod x_year 4) 0)))
 (let (($x835 (ite (or (and $x786 (and (distinct (mod x_year 100) 0) true)) $x235) $x571 $x627)))
 (let (($x575 (= x_month 2)))
 (ite $x575 $x835 true))))))))
(assert
 (let (($x442 (<= x_day 30)))
 (let (($x203 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x203 $x442 true))))
(assert
 (let (($x613 (= x_year 2022)))
 (let (($x455 (and $x613 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x455)))))
(assert
 (let (($x613 (= x_year 2022)))
(let (($x775 (and $x613 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x775)))))
(check-sat)
