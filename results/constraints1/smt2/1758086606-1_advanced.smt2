; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36584)))
(assert
 (<= x_days 36829))
(assert
 (>= x_days (- 2)))
(assert
 (<= x_days 0))
(assert
 (not (= x_days (- 2))))
(assert
 (not (= x_days 0)))
(check-sat)
