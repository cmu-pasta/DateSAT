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
 (let ((?x465 (+ x_months 24003)))
 (let ((?x518 (- ?x465 (* (div (- ?x465 1) 12) 12))))
 (let ((?x1769 (ite (or (= ?x518 4) (= ?x518 6) (= ?x518 9) (= ?x518 11)) 30 31)))
 (let (($x533 (and (= (mod (div (- ?x465 1) 12) 4) 0) (and (distinct (mod (div (- ?x465 1) 12) 100) 0) true))))
 (let ((?x494 (ite (or $x533 (= (mod (div (- ?x465 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x518 2) ?x494 ?x1769))))))))
(assert
 (let (($x1119 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x1119))))
(assert
 (let (($x1102 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x1102))))
(check-sat)
