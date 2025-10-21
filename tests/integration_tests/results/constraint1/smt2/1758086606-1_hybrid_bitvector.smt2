; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () (_ BitVec 32))
(assert
 (bvsle (_ bv4294930771 32) x_epoch))
(assert
 (bvsge (_ bv36523 32) x_epoch))
(assert
 (bvsge x_epoch (_ bv4294967294 32)))
(assert
 (bvsle x_epoch (_ bv0 32)))
(assert
 (not (= x_epoch (_ bv4294967294 32))))
(assert
 (not (= x_epoch (_ bv0 32))))
(check-sat)
