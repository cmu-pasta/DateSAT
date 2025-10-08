; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_months () Int)
(declare-fun x_beta () Int)
(assert
 (<= (- 1202) x_months))
(assert
 (>= 1209 x_months))
(assert
 (>= x_beta 0))
(assert
 (let ((?x2277 (+ x_months 24003)))
 (let ((?x2953 (- ?x2277 (* (div (- ?x2277 1) 12) 12))))
 (let ((?x2637 (ite (or (= ?x2953 4) (= ?x2953 6) (= ?x2953 9) (= ?x2953 11)) 30 31)))
 (let (($x1777 (and (= (mod (div (- ?x2277 1) 12) 4) 0) (and (distinct (mod (div (- ?x2277 1) 12) 100) 0) true))))
 (let ((?x936 (ite (or $x1777 (= (mod (div (- ?x2277 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x2953 2) ?x936 ?x2637))))))))
(assert
 (let ((?x4635 (- (+ (* 2000 12) 2) 24003)))
 (let (($x964 (= x_months ?x4635)))
 (or (> x_months ?x4635) (and $x964 (<= 27 x_beta))))))
(assert
 (let ((?x4580 (- (+ (* 2000 12) 3) 24003)))
 (let (($x4589 (= x_months ?x4580)))
 (or (< x_months ?x4580) (and $x4589 (>= 0 x_beta))))))
(assert
 (let ((?x4635 (- (+ (* 2000 12) 2) 24003)))
 (let (($x964 (= x_months ?x4635)))
 (not (and $x964 (= 27 x_beta))))))
(assert
 (let ((?x4580 (- (+ (* 2000 12) 3) 24003)))
(let (($x4589 (= x_months ?x4580)))
(not (and $x4589 (= 0 x_beta))))))
(check-sat)
