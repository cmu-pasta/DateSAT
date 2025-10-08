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
 (let (($x2619 (<= x_day 28)))
 (let (($x2219 (<= x_day 29)))
 (let (($x4856 (= (mod x_year 400) 0)))
 (let (($x2424 (= (mod x_year 4) 0)))
 (let (($x2191 (ite (or (and $x2424 (and (distinct (mod x_year 100) 0) true)) $x4856) $x2219 $x2619)))
 (let (($x1839 (= x_month 2)))
 (ite $x1839 $x2191 true))))))))
(assert
 (let (($x4478 (<= x_day 30)))
 (let (($x3556 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x3556 $x4478 true))))
(assert
 (let (($x1762 (= x_year 2022)))
 (let (($x766 (and $x1762 (or (< x_month 2) (and (= x_month 2) (<= x_day 28))))))
 (not (or (< x_year 2022) $x766)))))
(assert
 (let (($x1762 (= x_year 2022)))
(let (($x3021 (and $x1762 (or (> x_month 3) (and (= x_month 3) (>= x_day 1))))))
(not (or (> x_year 2022) $x3021)))))
(check-sat)
