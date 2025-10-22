; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_year () Int)
(declare-fun x_day () Int)
(assert
 (let (($x21735 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (let ((?x87719 (ite $x21735 30 31)))
 (let (($x2896 (= (mod x_year 400) 0)))
 (let (($x56709 (= (mod x_year 4) 0)))
 (let ((?x1291 (ite (or (and $x56709 (and (distinct (mod x_year 100) 0) true)) $x2896) 29 28)))
 (let (($x82619 (= x_month 2)))
 (let (($x58155 (<= x_day (ite $x82619 ?x1291 ?x87719))))
 (let (($x36256 (>= x_day 1)))
 (let (($x3518 (<= x_month 2)))
 (let (($x75583 (>= x_month 1)))
 (let (($x10842 (= x_year 2100)))
 (let (($x1148 (<= x_month 12)))
 (let (($x3459 (<= x_year 2099)))
 (let (($x76510 (>= x_year 1901)))
 (or (and (= x_year 1900) (>= x_month 3) $x1148 $x36256 $x58155) (and $x76510 $x3459 $x75583 $x1148 $x36256 $x58155) (and $x10842 $x75583 $x3518 $x36256 $x58155)))))))))))))))))
(assert
 (let (($x41170 (= x_year 2000)))
 (let (($x30170 (and $x41170 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x30170))))
(assert
 (let (($x41170 (= x_year 2000)))
 (let (($x82220 (and $x41170 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x82220))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
