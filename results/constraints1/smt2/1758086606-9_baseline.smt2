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
 (let (($x675 (<= x_day 28)))
 (let (($x554 (<= x_day 29)))
 (let (($x600 (= (mod x_year 400) 0)))
 (let (($x269 (= (mod x_year 4) 0)))
 (let (($x219 (ite (or (and $x269 (and (distinct (mod x_year 100) 0) true)) $x600) $x554 $x675)))
 (let (($x248 (= x_month 2)))
 (ite $x248 $x219 true))))))))
(assert
 (let (($x470 (<= x_day 30)))
 (let (($x478 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x478 $x470 true))))
(assert
 (>= y_month 1))
(assert
 (<= y_month 12))
(assert
 (>= y_day 1))
(assert
 (<= y_day 31))
(assert
 (let (($x663 (<= y_day 28)))
 (let (($x572 (<= y_day 29)))
 (let (($x661 (= (mod y_year 400) 0)))
 (let (($x506 (= (mod y_year 4) 0)))
 (let (($x521 (ite (or (and $x506 (and (distinct (mod y_year 100) 0) true)) $x661) $x572 $x663)))
 (let (($x692 (= y_month 2)))
 (ite $x692 $x521 true))))))))
(assert
 (let (($x398 (<= y_day 30)))
 (let (($x244 (or (= y_month 4) (= y_month 6) (= y_month 9) (= y_month 11))))
 (ite $x244 $x398 true))))
(assert
 (let (($x694 (= x_day 29)))
 (let (($x248 (= x_month 2)))
 (let (($x452 (= x_year 2020)))
 (and $x452 $x248 $x694)))))
(assert
 (let (($x650 (or (= (+ (mod (- (+ x_month 0) 1) 12) 1) 4) (= (+ (mod (- (+ x_month 0) 1) 12) 1) 6) (= (+ (mod (- (+ x_month 0) 1) 12) 1) 9) (= (+ (mod (- (+ x_month 0) 1) 12) 1) 11))))
 (let ((?x652 (+ (+ x_year 1) (div (- (+ x_month 0) 1) 12))))
 (let (($x645 (or (and (= (mod ?x652 4) 0) (and (distinct (mod ?x652 100) 0) true)) (= (mod ?x652 400) 0))))
 (let ((?x584 (ite (= (+ (mod (- (+ x_month 0) 1) 12) 1) 2) (ite $x645 29 28) (ite $x650 30 31))))
 (let ((?x204 (ite (< x_day 1) 1 (ite (> x_day ?x584) ?x584 x_day))))
 (let ((?x657 (ite (< ?x204 1) 1 (ite (> ?x204 ?x584) ?x584 ?x204))))
 (let ((?x304 (ite (< 2 (+ (mod (- (+ x_month 0) 1) 12) 1)) (- 3) 9)))
 (let ((?x653 (+ (mod (- (+ x_month 0) 1) 12) 1)))
 (let ((?x468 (- (+ ?x652 (* (div 0 146097) 400)) (ite (>= 2 ?x653) 1 0))))
 (let ((?x281 (ite (<= 0 ?x468) (div ?x468 400) (div (- ?x468 399) 400))))
 (let ((?x373 (- ?x468 (* ?x281 400))))
 (let ((?x156 (+ (- (+ (* ?x373 365) (div ?x373 4)) (div ?x373 100)) (- (+ (div (+ (* 153 (+ ?x653 ?x304)) 2) 5) ?x657) 1))))
 (let ((?x510 (+ (+ (* ?x281 146097) ?x156) (mod 0 146097))))
 (let ((?x690 (ite (<= 0 ?x510) (div ?x510 146097) (div (- ?x510 146096) 146097))))
 (let ((?x433 (- ?x510 (* ?x690 146097))))
 (let ((?x410 (div (+ (* 400 ?x433) 591) 146097)))
 (let ((?x473 (- ?x433 (- (+ (* 365 ?x410) (div ?x410 4)) (div ?x410 100)))))
 (let ((?x387 (div (+ (* 5 ?x473) 2) 153)))
 (let (($x301 (= 0 0)))
 (let ((?x396 (ite $x301 ?x657 (+ (- ?x473 (div (+ (* 153 ?x387) 2) 5)) 1))))
 (let (($x367 (= y_month (ite $x301 ?x653 (- (+ ?x387 3) (ite (> 10 ?x387) 0 12))))))
 (let ((?x325 (ite (>= 2 (- (+ ?x387 3) (ite (> 10 ?x387) 0 12))) 1 0)))
 (and (= y_year (ite $x301 ?x652 (+ (+ ?x410 (* ?x690 400)) ?x325))) $x367 (= y_day ?x396)))))))))))))))))))))))))
(assert
 (not (and (= y_year 2021) (= y_month 2) (= y_day 28))))
(check-sat)
