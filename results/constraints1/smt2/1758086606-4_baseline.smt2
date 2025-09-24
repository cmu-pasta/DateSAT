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
 (let (($x302 (<= x_day 28)))
 (let (($x223 (<= x_day 29)))
 (let (($x328 (= (mod x_year 400) 0)))
 (let (($x261 (= (mod x_year 4) 0)))
 (let (($x332 (ite (or (and $x261 (and (distinct (mod x_year 100) 0) true)) $x328) $x223 $x302)))
 (let (($x237 (= x_month 2)))
 (ite $x237 $x332 true))))))))
(assert
 (let (($x305 (<= x_day 30)))
 (let (($x303 (or (= x_month 4) (= x_month 6) (= x_month 9) (= x_month 11))))
 (ite $x303 $x305 true))))
(assert
 (>= y_month 1))
(assert
 (<= y_month 12))
(assert
 (>= y_day 1))
(assert
 (<= y_day 31))
(assert
 (let (($x201 (<= y_day 28)))
 (let (($x244 (<= y_day 29)))
 (let (($x204 (= (mod y_year 400) 0)))
 (let (($x292 (= (mod y_year 4) 0)))
 (let (($x214 (ite (or (and $x292 (and (distinct (mod y_year 100) 0) true)) $x204) $x244 $x201)))
 (let (($x212 (= y_month 2)))
 (ite $x212 $x214 true))))))))
(assert
 (let (($x345 (<= y_day 30)))
 (let (($x344 (or (= y_month 4) (= y_month 6) (= y_month 9) (= y_month 11))))
 (ite $x344 $x345 true))))
(assert
 (let (($x312 (= x_day 15)))
 (let (($x311 (= x_month 1)))
 (let (($x310 (= x_year 2022)))
 (and $x310 $x311 $x312)))))
(assert
 (let (($x387 (or (= (+ (mod (- (+ x_month 13) 1) 12) 1) 4) (= (+ (mod (- (+ x_month 13) 1) 12) 1) 6) (= (+ (mod (- (+ x_month 13) 1) 12) 1) 9) (= (+ (mod (- (+ x_month 13) 1) 12) 1) 11))))
 (let ((?x366 (+ (+ x_year 0) (div (- (+ x_month 13) 1) 12))))
 (let (($x357 (or (and (= (mod ?x366 4) 0) (and (distinct (mod ?x366 100) 0) true)) (= (mod ?x366 400) 0))))
 (let ((?x369 (ite (= (+ (mod (- (+ x_month 13) 1) 12) 1) 2) (ite $x357 29 28) (ite $x387 30 31))))
 (let ((?x373 (ite (< x_day 1) 1 (ite (> x_day ?x369) ?x369 x_day))))
 (let ((?x379 (ite (< ?x373 1) 1 (ite (> ?x373 ?x369) ?x369 ?x373))))
 (let ((?x385 (ite (< 2 (+ (mod (- (+ x_month 13) 1) 12) 1)) (- 3) 9)))
 (let ((?x367 (+ (mod (- (+ x_month 13) 1) 12) 1)))
 (let ((?x122 (- (+ ?x366 (* (div 40 146097) 400)) (ite (>= 2 ?x367) 1 0))))
 (let ((?x375 (ite (<= 0 ?x122) (div ?x122 400) (div (- ?x122 399) 400))))
 (let ((?x377 (- ?x122 (* ?x375 400))))
 (let ((?x191 (+ (- (+ (* ?x377 365) (div ?x377 4)) (div ?x377 100)) (- (+ (div (+ (* 153 (+ ?x367 ?x385)) 2) 5) ?x379) 1))))
 (let ((?x194 (+ (+ (* ?x375 146097) ?x191) (mod 40 146097))))
 (let ((?x151 (ite (<= 0 ?x194) (div ?x194 146097) (div (- ?x194 146096) 146097))))
 (let ((?x125 (- ?x194 (* ?x151 146097))))
 (let ((?x656 (div (+ (* 400 ?x125) 591) 146097)))
 (let ((?x642 (- ?x125 (- (+ (* 365 ?x656) (div ?x656 4)) (div ?x656 100)))))
 (let ((?x645 (div (+ (* 5 ?x642) 2) 153)))
 (let ((?x657 (+ (- ?x642 (div (+ (* 153 ?x645) 2) 5)) 1)))
 (let (($x381 (= 0 40)))
 (let (($x315 (= y_month (ite $x381 ?x367 (- (+ ?x645 3) (ite (> 10 ?x645) 0 12))))))
 (let ((?x329 (ite (>= 2 (- (+ ?x645 3) (ite (> 10 ?x645) 0 12))) 1 0)))
 (let ((?x358 (+ (+ ?x656 (* ?x151 400)) ?x329)))
 (and (= y_year (ite $x381 ?x366 ?x358)) $x315 (= y_day (ite $x381 ?x379 ?x657)))))))))))))))))))))))))))
(assert
 (not (and (= y_year 2023) (= y_month 2) (= y_day 24))))
(check-sat)
