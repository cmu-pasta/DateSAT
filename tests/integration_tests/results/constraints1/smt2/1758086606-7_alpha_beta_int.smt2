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
 (let ((?x3131 (+ x_months 24003)))
 (let ((?x1242 (- ?x3131 (* (div (- ?x3131 1) 12) 12))))
 (let ((?x658 (ite (or (= ?x1242 4) (= ?x1242 6) (= ?x1242 9) (= ?x1242 11)) 30 31)))
 (let (($x1184 (and (= (mod (div (- ?x3131 1) 12) 4) 0) (and (distinct (mod (div (- ?x3131 1) 12) 100) 0) true))))
 (let ((?x3432 (ite (or $x1184 (= (mod (div (- ?x3131 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x1242 2) ?x3432 ?x658))))))))
(assert
 (let (($x874 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x874))))
(assert
 (let (($x708 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x708))))
(check-sat)
