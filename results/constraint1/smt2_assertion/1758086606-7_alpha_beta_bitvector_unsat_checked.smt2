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
 (let ((?x424 (+ x_months 24003)))
 (let ((?x430 (- ?x424 (* (div (- ?x424 1) 12) 12))))
 (let ((?x449 (ite (or (= ?x430 4) (= ?x430 6) (= ?x430 9) (= ?x430 11)) 30 31)))
 (let (($x438 (and (= (mod (div (- ?x424 1) 12) 4) 0) (and (distinct (mod (div (- ?x424 1) 12) 100) 0) true))))
 (let ((?x443 (ite (or $x438 (= (mod (div (- ?x424 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x430 2) ?x443 ?x449))))))))
(assert
 (let (($x513 (and (= x_months (- (+ (* 2022 12) 2) 24003)) (>= 27 x_beta))))
 (not (or (< x_months (- (+ (* 2022 12) 2) 24003)) $x513))))
(assert
 (let (($x533 (and (= x_months (- (+ (* 2022 12) 3) 24003)) (<= 0 x_beta))))
(not (or (> x_months (- (+ (* 2022 12) 3) 24003)) $x533))))
(check-sat)
