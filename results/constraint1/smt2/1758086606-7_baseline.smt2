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
 (let (($x156 (<= x_day 28)))
 (let (($x115 (<= x_day 29)))
 (let (($x210 (= (mod x_year 400) 0)))
 (let (($x700 (= (mod x_year 4) 0)))
 (let (($x221 (ite (or (and $x700 (and (distinct (mod x_year 100) 0) true)) $x210) $x115 $x156)))
 (let (($x330 (= x_month 2)))
 (ite $x330 $x221 true))))))))
(assert
 (let (($x307 (<= x_day 30)))
 (let (($x779 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x779 $x307 true))))
(assert
 (let (($x175 (= x_year 2022)))
 (let (($x124 (and $x175 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x124)))))
(assert
 (let (($x175 (= x_year 2022)))
(let (($x388 (and $x175 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x388)))))
(check-sat)
