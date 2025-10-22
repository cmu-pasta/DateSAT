; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_year () Int)
(declare-fun x_day () Int)
(assert
 (let (($x419 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (let ((?x420 (ite $x419 30 31)))
 (let (($x412 (= (mod x_year 400) 0)))
 (let (($x405 (= (mod x_year 4) 0)))
 (let ((?x414 (ite (or (and $x405 (and (distinct (mod x_year 100) 0) true)) $x412) 29 28)))
 (let (($x403 (= x_month 2)))
 (let (($x422 (<= x_day (ite $x403 ?x414 ?x420))))
 (let (($x402 (>= x_day 1)))
 (let (($x432 (<= x_month 2)))
 (let (($x428 (>= x_month 1)))
 (let (($x431 (= x_year 2100)))
 (let (($x401 (<= x_month 12)))
 (let (($x427 (<= x_year 2099)))
 (let (($x425 (>= x_year 1901)))
 (or (and (= x_year 1900) (>= x_month 3) $x401 $x402 $x422) (and $x425 $x427 $x428 $x401 $x402 $x422) (and $x431 $x428 $x432 $x402 $x422)))))))))))))))))
(assert
 (let (($x468 (= x_year 2000)))
 (let (($x473 (and $x468 (or (> x_month 2) (and (= x_month 2) (>= x_day 28))))))
 (or (> x_year 2000) $x473))))
(assert
 (let (($x468 (= x_year 2000)))
 (let (($x487 (and $x468 (or (< x_month 3) (and (= x_month 3) (<= x_day 1))))))
 (or (< x_year 2000) $x487))))
(assert
 (not (and (= x_year 2000) (= x_month 2) (= x_day 28))))
(assert
 (not (and (= x_year 2000) (= x_month 3) (= x_day 1))))
(check-sat)
