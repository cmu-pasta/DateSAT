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
 (let ((?x3711 (+ x_months 24003)))
 (let ((?x2975 (- ?x3711 (* (div (- ?x3711 1) 12) 12))))
 (let ((?x1872 (ite (or (= ?x2975 4) (= ?x2975 6) (= ?x2975 9) (= ?x2975 11)) 30 31)))
 (let (($x1933 (and (= (mod (div (- ?x3711 1) 12) 4) 0) (and (distinct (mod (div (- ?x3711 1) 12) 100) 0) true))))
 (let ((?x2149 (ite (or $x1933 (= (mod (div (- ?x3711 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x2975 2) ?x2149 ?x1872))))))))
(assert
 (let ((?x5892 (- (+ (* 2000 12) 2) 24003)))
 (let (($x2182 (= x_months ?x5892)))
 (or (> x_months ?x5892) (and $x2182 (<= 27 x_beta))))))
(assert
 (let ((?x4676 (- (+ (* 2000 12) 3) 24003)))
 (let (($x5849 (= x_months ?x4676)))
 (or (< x_months ?x4676) (and $x5849 (>= 0 x_beta))))))
(assert
 (let ((?x5892 (- (+ (* 2000 12) 2) 24003)))
 (let (($x2182 (= x_months ?x5892)))
 (not (and $x2182 (= 27 x_beta))))))
(assert
 (let ((?x4676 (- (+ (* 2000 12) 3) 24003)))
(let (($x5849 (= x_months ?x4676)))
(not (and $x5849 (= 0 x_beta))))))
(check-sat)
