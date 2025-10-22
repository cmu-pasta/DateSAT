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
 (let ((?x616 (+ x_months 24003)))
 (let ((?x4017 (- ?x616 (* (div (- ?x616 1) 12) 12))))
 (let ((?x4207 (ite (or (= ?x4017 4) (= ?x4017 6) (= ?x4017 9) (= ?x4017 11)) 30 31)))
 (let (($x2587 (and (= (mod (div (- ?x616 1) 12) 4) 0) (and (distinct (mod (div (- ?x616 1) 12) 100) 0) true))))
 (let ((?x2405 (ite (or $x2587 (= (mod (div (- ?x616 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x4017 2) ?x2405 ?x4207))))))))
(assert
 (let (($x3082 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x3082))))
(assert
 (let (($x4243 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x4243))))
(check-sat)
