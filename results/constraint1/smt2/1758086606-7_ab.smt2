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
 (let ((?x3695 (+ x_months 24003)))
 (let ((?x4071 (- ?x3695 (* (div (- ?x3695 1) 12) 12))))
 (let ((?x2733 (ite (or (= ?x4071 4) (= ?x4071 6) (= ?x4071 9) (= ?x4071 11)) 30 31)))
 (let (($x4617 (and (= (mod (div (- ?x3695 1) 12) 4) 0) (and (distinct (mod (div (- ?x3695 1) 12) 100) 0) true))))
 (let ((?x1959 (ite (or $x4617 (= (mod (div (- ?x3695 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x4071 2) ?x1959 ?x2733))))))))
(assert
 (let (($x3592 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x3592))))
(assert
 (let (($x2341 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x2341))))
(check-sat)
