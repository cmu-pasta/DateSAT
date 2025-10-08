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
 (let (($x372 (<= x_day 28)))
 (let (($x695 (<= x_day 29)))
 (let (($x691 (= (mod x_year 400) 0)))
 (let (($x922 (= (mod x_year 4) 0)))
 (let (($x760 (ite (or (and $x922 (and (distinct (mod x_year 100) 0) true)) $x691) $x695 $x372)))
 (let (($x884 (= x_month 2)))
 (ite $x884 $x760 true))))))))
(assert
 (let (($x773 (<= x_day 30)))
 (let (($x848 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x848 $x773 true))))
(assert
 (let (($x307 (= x_year 2022)))
 (let (($x258 (and $x307 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x258)))))
(assert
 (let (($x307 (= x_year 2022)))
(let (($x215 (and $x307 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x215)))))
(check-sat)
