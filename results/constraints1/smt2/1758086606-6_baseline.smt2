; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () Int)
(declare-fun x_day () Int)
(declare-fun x_year () Int)
(declare-fun y_month () Int)
(declare-fun y_day () Int)
(declare-fun y_year () Int)
(assert
 (>= x_month 1))
(assert
 (<= x_month 12))
(assert
 (>= x_day 1))
(assert
 (<= x_day 31))
(assert
 (let (($x544 (<= x_day 28)))
 (let (($x478 (<= x_day 29)))
 (let (($x492 (= (mod x_year 400) 0)))
 (let (($x675 (= (mod x_year 4) 0)))
 (let (($x500 (ite (or (and $x675 (and (distinct (mod x_year 100) 0) true)) $x492) $x478 $x544)))
 (let (($x554 (= x_month 2)))
 (ite $x554 $x500 true))))))))
(assert
 (let (($x393 (<= x_day 30)))
 (let (($x600 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x600 $x393 true))))
(assert
 (>= y_month 1))
(assert
 (<= y_month 12))
(assert
 (>= y_day 1))
(assert
 (<= y_day 31))
(assert
 (let (($x499 (<= y_day 28)))
 (let (($x250 (<= y_day 29)))
 (let (($x649 (= (mod y_year 400) 0)))
 (let (($x463 (= (mod y_year 4) 0)))
 (let (($x112 (ite (or (and $x463 (and (distinct (mod y_year 100) 0) true)) $x649) $x250 $x499)))
 (let (($x672 (= y_month 2)))
 (ite $x672 $x112 true))))))))
(assert
 (let (($x118 (<= y_day 30)))
 (let (($x446 (= y_month 4)))
 (let (($x427 (or $x446 (= y_month 6) (= y_month 9) (= y_month 11))))
 (ite $x427 $x118 true)))))
(assert
 (let (($x665 (= x_day 31)))
 (let (($x626 (= x_month 1)))
 (let (($x664 (= x_year 2023)))
 (and $x664 $x626 $x665)))))
(assert
 (let (($x264 (or (= (+ (mod (- (+ x_month 3) 1) 12) 1) 4) (= (+ (mod (- (+ x_month 3) 1) 12) 1) 6) (= (+ (mod (- (+ x_month 3) 1) 12) 1) 9) (= (+ (mod (- (+ x_month 3) 1) 12) 1) 11))))
 (let ((?x615 (+ (+ x_year 0) (div (- (+ x_month 3) 1) 12))))
 (let (($x528 (or (and (= (mod ?x615 4) 0) (and (distinct (mod ?x615 100) 0) true)) (= (mod ?x615 400) 0))))
 (let ((?x328 (ite (= (+ (mod (- (+ x_month 3) 1) 12) 1) 2) (ite $x528 29 28) (ite $x264 30 31))))
 (let ((?x302 (ite (< x_day 1) 1 (ite (> x_day ?x328) ?x328 x_day))))
 (let ((?x583 (ite (< ?x302 1) 1 (ite (> ?x302 ?x328) ?x328 ?x302))))
 (let ((?x309 (ite (< 2 (+ (mod (- (+ x_month 3) 1) 12) 1)) (- 3) 9)))
 (let ((?x503 (+ (mod (- (+ x_month 3) 1) 12) 1)))
 (let ((?x435 (- (+ ?x615 (* (div 0 146097) 400)) (ite (>= 2 ?x503) 1 0))))
 (let ((?x127 (ite (<= 0 ?x435) (div ?x435 400) (div (- ?x435 399) 400))))
 (let ((?x608 (- ?x435 (* ?x127 400))))
 (let ((?x647 (+ (- (+ (* ?x608 365) (div ?x608 4)) (div ?x608 100)) (- (+ (div (+ (* 153 (+ ?x503 ?x309)) 2) 5) ?x583) 1))))
 (let ((?x105 (+ (+ (* ?x127 146097) ?x647) (mod 0 146097))))
 (let ((?x109 (ite (<= 0 ?x105) (div ?x105 146097) (div (- ?x105 146096) 146097))))
 (let ((?x184 (- ?x105 (* ?x109 146097))))
 (let ((?x602 (div (+ (* 400 ?x184) 591) 146097)))
 (let ((?x610 (- ?x184 (- (+ (* 365 ?x602) (div ?x602 4)) (div ?x602 100)))))
 (let ((?x564 (div (+ (* 5 ?x610) 2) 153)))
 (let (($x535 (= 0 0)))
 (let ((?x592 (ite $x535 ?x583 (+ (- ?x610 (div (+ (* 153 ?x564) 2) 5)) 1))))
 (let (($x539 (= y_month (ite $x535 ?x503 (- (+ ?x564 3) (ite (> 10 ?x564) 0 12))))))
 (let ((?x474 (ite (>= 2 (- (+ ?x564 3) (ite (> 10 ?x564) 0 12))) 1 0)))
 (and (= y_year (ite $x535 ?x615 (+ (+ ?x602 (* ?x109 400)) ?x474))) $x539 (= y_day ?x592)))))))))))))))))))))))))
(assert
 (let (($x146 (= y_day 30)))
(let (($x446 (= y_month 4)))
(let (($x661 (= y_year 2023)))
(and $x661 $x446 $x146)))))
(check-sat)
