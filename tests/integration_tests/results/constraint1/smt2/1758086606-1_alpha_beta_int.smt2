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
 (let ((?x2066 (+ x_months 24003)))
 (let ((?x1873 (- ?x2066 (* (div (- ?x2066 1) 12) 12))))
 (let ((?x1579 (ite (or (= ?x1873 4) (= ?x1873 6) (= ?x1873 9) (= ?x1873 11)) 30 31)))
 (let (($x2888 (and (= (mod (div (- ?x2066 1) 12) 4) 0) (and (distinct (mod (div (- ?x2066 1) 12) 100) 0) true))))
 (let ((?x3884 (ite (or $x2888 (= (mod (div (- ?x2066 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x1873 2) ?x3884 ?x1579))))))))
(assert
 (let ((?x5849 (- (+ (* 2000 12) 2) 24003)))
 (let (($x3740 (= x_months ?x5849)))
 (or (> x_months ?x5849) (and $x3740 (<= 27 x_beta))))))
(assert
 (let ((?x4741 (- (+ (* 2000 12) 3) 24003)))
 (let (($x5806 (= x_months ?x4741)))
 (or (< x_months ?x4741) (and $x5806 (>= 0 x_beta))))))
(assert
 (let ((?x5849 (- (+ (* 2000 12) 2) 24003)))
 (let (($x3740 (= x_months ?x5849)))
 (not (and $x3740 (= 27 x_beta))))))
(assert
 (let ((?x4741 (- (+ (* 2000 12) 3) 24003)))
(let (($x5806 (= x_months ?x4741)))
(not (and $x5806 (= 0 x_beta))))))
(check-sat)
