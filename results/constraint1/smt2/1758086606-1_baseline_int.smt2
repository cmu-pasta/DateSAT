; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_year () Int)
(declare-fun x_day () Int)
(assert
 (let (($x425 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (let ((?x426 (ite $x425 30 31)))
 (let (($x418 (= (mod x_year 400) 0)))
 (let (($x411 (= (mod x_year 4) 0)))
 (let ((?x420 (ite (or (and $x411 (and (distinct (mod x_year 100) 0) true)) $x418) 29 28)))
 (let (($x409 (= x_month 2)))
 (let (($x428 (<= x_day (ite $x409 ?x420 ?x426))))
 (let (($x408 (>= x_day 1)))
 (let (($x438 (<= x_month 2)))
 (let (($x434 (>= x_month 1)))
 (let (($x437 (= x_year 2100)))
 (let (($x407 (<= x_month 12)))
 (let (($x433 (<= x_year 2099)))
 (let (($x431 (>= x_year 1901)))
 (or (and (= x_year 1900) (>= x_month 3) $x407 $x408 $x428) (and $x431 $x433 $x434 $x407 $x408 $x428) (and $x437 $x434 $x438 $x408 $x428)))))))))))))))))
(assert
 (let (($x474 (= x_year 2000)))
 (let (($x479 (and $x474 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x479))))
(assert
 (let (($x474 (= x_year 2000)))
 (let (($x493 (and $x474 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x493))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
