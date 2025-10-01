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
 (let (($x116 (<= x_day 28)))
 (let (($x792 (<= x_day 29)))
 (let (($x617 (= (mod x_year 400) 0)))
 (let (($x690 (= (mod x_year 4) 0)))
 (let (($x771 (ite (or (and $x690 (and (distinct (mod x_year 100) 0) true)) $x617) $x792 $x116)))
 (let (($x433 (= x_month 2)))
 (ite $x433 $x771 true))))))))
(assert
 (let (($x666 (<= x_day 30)))
 (let (($x130 (= x_month 4)))
 (let (($x442 (or $x130 (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x442 $x666 true)))))
(assert
 (let (($x601 (= x_year 2023)))
 (let (($x807 (and $x601 (or (< x_month 4) (and (= x_month 4) (<= x_day 30))))))
 (not (or (< x_year 2023) $x807)))))
(assert
 (let (($x601 (= x_year 2023)))
(let (($x245 (and $x601 (or (> x_month 5) (and (= x_month 5) (>= x_day 1))))))
(not (or (> x_year 2023) $x245)))))
(check-sat)
