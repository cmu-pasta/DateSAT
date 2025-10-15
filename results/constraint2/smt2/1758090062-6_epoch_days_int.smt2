; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(assert
 (>= x_days (- 36525)))
(assert
 (<= x_days 36523))
(assert
 (>= x_days 7303))
(assert
 (<= x_days 7305))
(assert
 (= (+ x_days 1) 7305))
(check-sat)
