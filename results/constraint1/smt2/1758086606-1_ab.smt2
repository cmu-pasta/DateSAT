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
 (let ((?x1821 (div (- (+ x_months (+ (* 2000 12) 3)) 1) 12)))
 (let ((?x10 (* 2000 12)))
 (let ((?x11 (+ ?x10 3)))
 (let ((?x479 (+ x_months ?x11)))
 (let ((?x1021 (- ?x479 (* ?x1821 12))))
 (let ((?x358 (ite (or (= ?x1021 4) (= ?x1021 6) (= ?x1021 9) (= ?x1021 11)) 30 31)))
 (let (($x3643 (or (and (= (mod ?x1821 4) 0) (and (distinct (mod ?x1821 100) 0) true)) (= (mod ?x1821 400) 0))))
 (< x_beta (ite (= ?x1021 2) (ite $x3643 29 28) ?x358))))))))))
(assert
 (let ((?x10 (* 2000 12)))
 (let ((?x11 (+ ?x10 3)))
 (let ((?x971 (- (+ ?x10 2) ?x11)))
 (let (($x3101 (= x_months ?x971)))
 (or (> x_months ?x971) (and $x3101 (<= 27 x_beta))))))))
(assert
 (let ((?x10 (* 2000 12)))
 (let ((?x11 (+ ?x10 3)))
 (let ((?x4104 (- ?x11 ?x11)))
 (let (($x2569 (= x_months ?x4104)))
 (or (< x_months ?x4104) (and $x2569 (>= 0 x_beta))))))))
(assert
 (let ((?x10 (* 2000 12)))
 (let ((?x11 (+ ?x10 3)))
 (let ((?x971 (- (+ ?x10 2) ?x11)))
 (let (($x3101 (= x_months ?x971)))
 (not (and $x3101 (= 27 x_beta))))))))
(assert
 (let ((?x10 (* 2000 12)))
(let ((?x11 (+ ?x10 3)))
(let ((?x4104 (- ?x11 ?x11)))
(let (($x2569 (= x_months ?x4104)))
(not (and $x2569 (= 0 x_beta))))))))
(check-sat)
