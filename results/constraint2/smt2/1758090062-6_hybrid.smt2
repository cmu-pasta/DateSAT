; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () Int)
(declare-fun x_plus_epoch () Int)
(assert
 (>= x_epoch (- 36584)))
(assert
 (<= x_epoch 36829))
(assert
 (>= x_epoch 7303))
(assert
 (<= x_epoch 7305))
(assert
 (>= x_plus_epoch (- 36584)))
(assert
 (<= x_plus_epoch 36829))
(assert
 (= x_plus_epoch (+ x_epoch 1)))
(assert
 (= x_plus_epoch 7305))
(check-sat)
