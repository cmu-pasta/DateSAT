; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () Int)
(declare-fun p_days () Int)
(declare-fun q_days () Int)
(declare-fun x_plus_period_866959_epoch () Int)
(declare-fun x_plus_period_866959_plus_period_867061_epoch () Int)
(assert
 (>= x_epoch (- 36584)))
(assert
 (<= x_epoch 36829))
(assert
 (= x_epoch (- 60)))
(assert
 (= p_days 390))
(assert
 (= q_days 400))
(assert
 (>= x_plus_period_866959_epoch (- 36584)))
(assert
 (<= x_plus_period_866959_epoch 36829))
(assert
 (= x_plus_period_866959_epoch (+ x_epoch p_days)))
(assert
 (>= x_plus_period_866959_plus_period_867061_epoch (- 36584)))
(assert
 (<= x_plus_period_866959_plus_period_867061_epoch 36829))
(assert
 (= x_plus_period_866959_plus_period_867061_epoch (+ x_plus_period_866959_epoch q_days)))
(assert
 (= x_plus_period_866959_plus_period_867061_epoch 370))
(check-sat)
