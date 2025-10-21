; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_epoch () (_ BitVec 32))
(assert
 (bvsle (_ bv4294930771 32) x_epoch))
(assert
 (bvsge (_ bv36523 32) x_epoch))
(assert
 (not (bvsle x_epoch (_ bv8034 32))))
(assert
 (not (bvsge x_epoch (_ bv8035 32))))
(check-sat)
