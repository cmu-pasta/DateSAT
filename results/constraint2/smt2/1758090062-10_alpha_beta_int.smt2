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
 (let ((?x3697 (+ x_months 24003)))
 (let ((?x789 (- ?x3697 (* (div (- ?x3697 1) 12) 12))))
 (let ((?x653 (ite (or (= ?x789 4) (= ?x789 6) (= ?x789 9) (= ?x789 11)) 30 31)))
 (let (($x2507 (and (= (mod (div (- ?x3697 1) 12) 4) 0) (and (distinct (mod (div (- ?x3697 1) 12) 100) 0) true))))
 (let ((?x4336 (ite (or $x2507 (= (mod (div (- ?x3697 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x789 2) ?x4336 ?x653))))))))
(assert
 (let (($x2053 (and (= x_months (- (+ (* 2023 12) 4) 24003)) (>= 29 x_beta))))
 (not (or (< x_months (- (+ (* 2023 12) 4) 24003)) $x2053))))
(assert
 (let (($x4356 (and (= x_months (- (+ (* 2023 12) 5) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2023 12) 5) 24003)) $x4356))))
(check-sat)
