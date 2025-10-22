; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () (_ BitVec 32))
(assert
 (bvsle (_ bv4294930771 32) x_days))
(assert
 (bvsge (_ bv36523 32) x_days))
(assert
 (bvsge x_days (_ bv4294967294 32)))
(assert
 (bvsle x_days (_ bv0 32)))
(assert
 (not (= x_days (_ bv4294967294 32))))
(assert
 (not (= x_days (_ bv0 32))))
(check-sat)
