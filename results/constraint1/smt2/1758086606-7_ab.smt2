; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_months () Int)
(declare-fun x_beta () Int)
(assert
 (>= x_months (- 1202)))
(assert
 (<= x_months 1209))
(assert
 (>= x_beta 0))
(assert
 (let ((?x3347 (div (- (+ x_months (+ (* 2000 12) 3)) 1) 12)))
 (let ((?x11 (+ (* 2000 12) 3)))
 (let ((?x1600 (+ x_months ?x11)))
 (let ((?x531 (- ?x1600 (* ?x3347 12))))
 (let ((?x1046 (ite (or (= ?x531 4) (= ?x531 6) (= ?x531 9) (= ?x531 11)) 30 31)))
 (let (($x2007 (or (and (= (mod ?x3347 4) 0) (and (distinct (mod ?x3347 100) 0) true)) (= (mod ?x3347 400) 0))))
 (< x_beta (ite (= ?x531 2) (ite $x2007 29 28) ?x1046)))))))))
(assert
 (let ((?x11 (+ (* 2000 12) 3)))
 (let ((?x2259 (- (+ (* 2022 12) 2) ?x11)))
 (let (($x3916 (or (< x_months ?x2259) (and (= x_months ?x2259) (>= 27 x_beta)))))
 (not $x3916)))))
(assert
 (let ((?x11 (+ (* 2000 12) 3)))
(let ((?x2702 (- (+ (* 2022 12) 3) ?x11)))
(let (($x1540 (or (> x_months ?x2702) (and (= x_months ?x2702) (<= 0 x_beta)))))
(not $x1540)))))
(check-sat)
