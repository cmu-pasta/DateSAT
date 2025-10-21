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
 (let ((?x5045 (+ x_months 24003)))
 (let ((?x4928 (- ?x5045 (* (div (- ?x5045 1) 12) 12))))
 (let ((?x2888 (ite (or (= ?x4928 4) (= ?x4928 6) (= ?x4928 9) (= ?x4928 11)) 30 31)))
 (let (($x4378 (and (= (mod (div (- ?x5045 1) 12) 4) 0) (and (distinct (mod (div (- ?x5045 1) 12) 100) 0) true))))
 (let ((?x5664 (ite (or $x4378 (= (mod (div (- ?x5045 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x4928 2) ?x5664 ?x2888))))))))
(assert
 (let (($x5096 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x5096))))
(assert
 (let (($x1827 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x1827))))
(check-sat)
