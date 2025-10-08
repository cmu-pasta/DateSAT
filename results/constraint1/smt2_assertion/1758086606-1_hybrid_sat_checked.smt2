; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () Int)
(assert
 (>= x_epoch (- 36584)))
(assert
 (<= x_epoch 36829))
(assert
 (>= x_epoch (- 2)))
(assert
 (<= x_epoch 0))
(assert
 (not (= x_epoch (- 2))))
(assert
 (not (= x_epoch 0)))
(assert
 (= x_epoch (- 1)))
(check-sat)
