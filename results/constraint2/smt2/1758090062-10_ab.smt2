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
 (let ((?x493 (+ x_months 24003)))
 (let ((?x3978 (- ?x493 (* (div (- ?x493 1) 12) 12))))
 (let ((?x4178 (ite (or (= ?x3978 4) (= ?x3978 6) (= ?x3978 9) (= ?x3978 11)) 30 31)))
 (let (($x533 (and (= (mod (div (- ?x493 1) 12) 4) 0) (and (distinct (mod (div (- ?x493 1) 12) 100) 0) true))))
 (let ((?x3696 (ite (or $x533 (= (mod (div (- ?x493 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x3978 2) ?x3696 ?x4178))))))))
(assert
 (let (($x3189 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x3189))))
(assert
 (let (($x2002 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x2002))))
(check-sat)
