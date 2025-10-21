; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_year () Int)
(declare-fun x_day () Int)
(assert
 (let (($x2114 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (let ((?x29762 (ite $x2114 30 31)))
 (let (($x2848 (= (mod x_year 400) 0)))
 (let (($x6772 (= (mod x_year 4) 0)))
 (let ((?x6180 (ite (or (and $x6772 (and (distinct (mod x_year 100) 0) true)) $x2848) 29 28)))
 (let (($x6073 (= x_month 2)))
 (let (($x6871 (<= x_day (ite $x6073 ?x6180 ?x29762))))
 (let (($x3308 (>= x_day 1)))
 (let (($x40014 (<= x_month 2)))
 (let (($x4571 (>= x_month 1)))
 (let (($x36216 (= x_year 2100)))
 (let (($x1542 (<= x_month 12)))
 (let (($x5220 (<= x_year 2099)))
 (let (($x4870 (>= x_year 1901)))
 (or (and (= x_year 1900) (>= x_month 3) $x1542 $x3308 $x6871) (and $x4870 $x5220 $x4571 $x1542 $x3308 $x6871) (and $x36216 $x4571 $x40014 $x3308 $x6871)))))))))))))))))
(assert
 (let (($x32853 (= x_year 2000)))
 (let (($x2125 (and $x32853 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x2125))))
(assert
 (let (($x32853 (= x_year 2000)))
 (let (($x815 (and $x32853 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x815))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
