; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36525)))
(assert
 (<= x_days 36525))
(assert
 (> x_days 8034))
(assert
 (< x_days 8035))
(check-sat)
