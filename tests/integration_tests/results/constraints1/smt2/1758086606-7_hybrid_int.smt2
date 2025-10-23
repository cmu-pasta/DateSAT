; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () Int)
(assert
 (>= x_epoch (- 36525)))
(assert
 (<= x_epoch 36523))
(assert
 (not (<= x_epoch 8034)))
(assert
 (not (>= x_epoch 8035)))
(check-sat)
