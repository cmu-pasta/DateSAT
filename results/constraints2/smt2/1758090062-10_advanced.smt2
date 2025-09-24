; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36525)))
(assert
 (<= x_days 36525))
(assert
 (> x_days 8460))
(assert
 (< x_days 8461))
(check-sat)
