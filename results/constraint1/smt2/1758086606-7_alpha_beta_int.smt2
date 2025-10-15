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
 (let ((?x3579 (+ x_months 24003)))
 (let ((?x2913 (- ?x3579 (* (div (- ?x3579 1) 12) 12))))
 (let ((?x3428 (ite (or (= ?x2913 4) (= ?x2913 6) (= ?x2913 9) (= ?x2913 11)) 30 31)))
 (let (($x3243 (and (= (mod (div (- ?x3579 1) 12) 4) 0) (and (distinct (mod (div (- ?x3579 1) 12) 100) 0) true))))
 (let ((?x1243 (ite (or $x3243 (= (mod (div (- ?x3579 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x2913 2) ?x1243 ?x3428))))))))
(assert
 (let (($x1747 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x1747))))
(assert
 (let (($x600 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x600))))
(check-sat)
