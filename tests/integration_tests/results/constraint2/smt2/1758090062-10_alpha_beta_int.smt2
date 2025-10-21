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
 (let ((?x4799 (+ x_months 24003)))
 (let ((?x2070 (- ?x4799 (* (div (- ?x4799 1) 12) 12))))
 (let ((?x3758 (ite (or (= ?x2070 4) (= ?x2070 6) (= ?x2070 9) (= ?x2070 11)) 30 31)))
 (let (($x4388 (and (= (mod (div (- ?x4799 1) 12) 4) 0) (and (distinct (mod (div (- ?x4799 1) 12) 100) 0) true))))
 (let ((?x782 (ite (or $x4388 (= (mod (div (- ?x4799 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x2070 2) ?x782 ?x3758))))))))
(assert
 (let (($x1417 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x1417))))
(assert
 (let (($x869 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x869))))
(check-sat)
