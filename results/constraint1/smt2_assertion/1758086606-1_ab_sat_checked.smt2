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
 (let ((?x226 (+ x_months 24003)))
 (let ((?x232 (- ?x226 (* (div (- ?x226 1) 12) 12))))
 (let ((?x251 (ite (or (= ?x232 4) (= ?x232 6) (= ?x232 9) (= ?x232 11)) 30 31)))
 (let (($x240 (and (= (mod (div (- ?x226 1) 12) 4) 0) (and (distinct (mod (div (- ?x226 1) 12) 100) 0) true))))
 (let ((?x245 (ite (or $x240 (= (mod (div (- ?x226 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x232 2) ?x245 ?x251))))))))
(assert
 (let ((?x310 (- (+ (* 2000 12) 2) 24003)))
 (let (($x312 (= x_months ?x310)))
 (or (> x_months ?x310) (and $x312 (<= 27 x_beta))))))
(assert
 (let ((?x325 (- (+ (* 2000 12) 3) 24003)))
 (let (($x327 (= x_months ?x325)))
 (or (< x_months ?x325) (and $x327 (>= 0 x_beta))))))
(assert
 (let ((?x310 (- (+ (* 2000 12) 2) 24003)))
 (let (($x312 (= x_months ?x310)))
 (not (and $x312 (= 27 x_beta))))))
(assert
 (let ((?x325 (- (+ (* 2000 12) 3) 24003)))
 (let (($x327 (= x_months ?x325)))
 (not (and $x327 (= 0 x_beta))))))
(assert
 (let ((?x310 (- (+ (* 2000 12) 2) 24003)))
(let (($x312 (= x_months ?x310)))
(and $x312 (= 28 x_beta)))))
(check-sat)
