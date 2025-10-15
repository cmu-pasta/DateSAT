; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_months () Int)
(declare-fun x_beta () Int)
(assert
 (<= (- 1200) x_months))
(assert
 (>= 1199 x_months))
(assert
 (>= x_beta 0))
(assert
 (let ((?x2657 (+ x_months 24003)))
 (let ((?x3009 (- ?x2657 (* (div (- ?x2657 1) 12) 12))))
 (let ((?x3598 (ite (or (= ?x3009 4) (= ?x3009 6) (= ?x3009 9) (= ?x3009 11)) 30 31)))
 (let (($x774 (and (= (mod (div (- ?x2657 1) 12) 4) 0) (and (distinct (mod (div (- ?x2657 1) 12) 100) 0) true))))
 (let ((?x486 (ite (or $x774 (= (mod (div (- ?x2657 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x3009 2) ?x486 ?x3598))))))))
(assert
 (let ((?x3863 (- (+ (* 2000 12) 2) 24003)))
 (let (($x2523 (= x_months ?x3863)))
 (or (> x_months ?x3863) (and $x2523 (<= 27 x_beta))))))
(assert
 (let ((?x4059 (- (+ (* 2000 12) 3) 24003)))
 (let (($x2420 (= x_months ?x4059)))
 (or (< x_months ?x4059) (and $x2420 (>= 0 x_beta))))))
(assert
 (let ((?x3863 (- (+ (* 2000 12) 2) 24003)))
 (let (($x2523 (= x_months ?x3863)))
 (not (and $x2523 (= 27 x_beta))))))
(assert
 (let ((?x4059 (- (+ (* 2000 12) 3) 24003)))
(let (($x2420 (= x_months ?x4059)))
(not (and $x2420 (= 0 x_beta))))))
(check-sat)
