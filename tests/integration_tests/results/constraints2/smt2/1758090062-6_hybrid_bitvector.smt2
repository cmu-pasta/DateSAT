; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () (_ BitVec 32))
(declare-fun x_plus_epoch () (_ BitVec 32))
(assert
 (bvsle (_ bv4294930771 32) x_epoch))
(assert
 (bvsge (_ bv36523 32) x_epoch))
(assert
 (bvsge x_epoch (_ bv7303 32)))
(assert
 (bvsle x_epoch (_ bv7305 32)))
(assert
 (bvsle (_ bv4294930771 32) x_plus_epoch))
(assert
 (bvsge (_ bv36523 32) x_plus_epoch))
(assert
 (= x_plus_epoch (bvadd x_epoch (_ bv1 32))))
(assert
 (= x_plus_epoch (_ bv7305 32)))
(check-sat)
