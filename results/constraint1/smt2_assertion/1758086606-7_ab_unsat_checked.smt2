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
 (let ((?x4065 (+ x_months 24003)))
 (let ((?x3537 (- ?x4065 (* (div (- ?x4065 1) 12) 12))))
 (let ((?x2607 (ite (or (= ?x3537 4) (= ?x3537 6) (= ?x3537 9) (= ?x3537 11)) 30 31)))
 (let (($x4808 (and (= (mod (div (- ?x4065 1) 12) 4) 0) (and (distinct (mod (div (- ?x4065 1) 12) 100) 0) true))))
 (let ((?x3127 (ite (or $x4808 (= (mod (div (- ?x4065 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x3537 2) ?x3127 ?x2607))))))))
(assert
 (let (($x2424 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x2424))))
(assert
 (let (($x2619 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x2619))))
(check-sat)
