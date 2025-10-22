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
 (let ((?x470 (+ x_months 24003)))
 (let ((?x2867 (- ?x470 (* (div (- ?x470 1) 12) 12))))
 (let ((?x496 (ite (or (= ?x2867 4) (= ?x2867 6) (= ?x2867 9) (= ?x2867 11)) 30 31)))
 (let (($x1339 (and (= (mod (div (- ?x470 1) 12) 4) 0) (and (distinct (mod (div (- ?x470 1) 12) 100) 0) true))))
 (let ((?x2691 (ite (or $x1339 (= (mod (div (- ?x470 1) 12) 400) 0)) 29 28)))
 (< x_beta (ite (= ?x2867 2) ?x2691 ?x496))))))))
(assert
 (let ((?x541 (- (+ (* 2000 12) 2) 24003)))
 (let (($x1885 (= x_months ?x541)))
 (or (> x_months ?x541) (and $x1885 (<= 27 x_beta))))))
(assert
 (let ((?x604 (- (+ (* 2000 12) 3) 24003)))
 (let (($x1246 (= x_months ?x604)))
 (or (< x_months ?x604) (and $x1246 (>= 0 x_beta))))))
(assert
 (let ((?x541 (- (+ (* 2000 12) 2) 24003)))
 (let (($x1885 (= x_months ?x541)))
 (not (and $x1885 (= 27 x_beta))))))
(assert
 (let ((?x604 (- (+ (* 2000 12) 3) 24003)))
(let (($x1246 (= x_months ?x604)))
(not (and $x1246 (= 0 x_beta))))))
(check-sat)
