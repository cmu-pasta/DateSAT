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
 (let ((?x1036 (+ x_months 24003)))
 (let ((?x4098 (- ?x1036 (* (div (- ?x1036 1) 12) 12))))
 (let ((?x1972 (ite (or (= ?x4098 4) (= ?x4098 6) (= ?x4098 9) (= ?x4098 11)) 30 31)))
 (let (($x3638 (and (= (mod (div (- ?x1036 1) 12) 4) 0) (and (distinct (mod (div (- ?x1036 1) 12) 100) 0) true))))
 (let ((?x3543 (ite (or $x3638 (= (mod (div (- ?x1036 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x4098 2) ?x3543 ?x1972))))))))
(assert
 (let (($x1600 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x1600))))
(assert
 (let (($x3804 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x3804))))
(check-sat)
