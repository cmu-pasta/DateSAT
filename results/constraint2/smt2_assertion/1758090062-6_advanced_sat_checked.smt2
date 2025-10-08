; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36584)))
(assert
 (<= x_days 36829))
(assert
 (>= x_days 7303))
(assert
 (<= x_days 7305))
(assert
 (= (+ x_days 1) 7305))
(assert
 (= x_days 7304))
(check-sat)
