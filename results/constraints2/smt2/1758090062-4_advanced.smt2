; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () Int)
(declare-fun p_days () Int)
(declare-fun q_days () Int)
(assert
 (>= x_days (- 36584)))
(assert
 (<= x_days 36829))
(assert
 (= x_days (- 60)))
(assert
 (= p_days 390))
(assert
 (= q_days 400))
(assert
 (= (+ (+ x_days p_days) q_days) 370))
(check-sat)
