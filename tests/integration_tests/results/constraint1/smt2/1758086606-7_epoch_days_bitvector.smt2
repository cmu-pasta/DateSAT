; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_days () (_ BitVec 32))
(assert
 (bvsle (_ bv4294930771 32) x_days))
(assert
 (bvsge (_ bv36523 32) x_days))
(assert
 (not (bvsle x_days (_ bv8034 32))))
(assert
 (not (bvsge x_days (_ bv8035 32))))
(check-sat)
