; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36525)))
(assert
 (<= x_days 36525))
(assert
 (>= x_days (- 2)))
(assert
 (<= x_days 0))
(assert
 (not (= x_days (- 2))))
(assert
 (not (= x_days 0)))
(check-sat)
