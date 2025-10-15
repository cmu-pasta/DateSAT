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
 (let ((?x2373 (+ x_months 24003)))
 (let ((?x5387 (- ?x2373 (* (div (- ?x2373 1) 12) 12))))
 (let ((?x577 (ite (or (= ?x5387 4) (= ?x5387 6) (= ?x5387 9) (= ?x5387 11)) 30 31)))
 (let (($x4907 (and (= (mod (div (- ?x2373 1) 12) 4) 0) (and (distinct (mod (div (- ?x2373 1) 12) 100) 0) true))))
 (let ((?x3947 (ite (or $x4907 (= (mod (div (- ?x2373 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x5387 2) ?x3947 ?x577))))))))
(assert
 (let (($x5150 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x5150))))
(assert
 (let (($x2312 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x2312))))
(check-sat)
