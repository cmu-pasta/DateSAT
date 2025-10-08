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
 (let (($x388 (<= x_day 28)))
 (let (($x921 (<= x_day 29)))
 (let (($x920 (= (mod x_year 400) 0)))
 (let (($x214 (= (mod x_year 4) 0)))
 (let (($x237 (ite (or (and $x214 (and (distinct (mod x_year 100) 0) true)) $x920) $x921 $x388)))
 (let (($x251 (= x_month 2)))
 (ite $x251 $x237 true))))))))
(assert
 (let (($x778 (<= x_day 30)))
 (let (($x932 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x932 $x778 true))))
(assert
 (let (($x309 (= x_year 2022)))
 (let (($x378 (and $x309 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x378)))))
(assert
 (let (($x309 (= x_year 2022)))
(let (($x338 (and $x309 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x338)))))
(check-sat)
