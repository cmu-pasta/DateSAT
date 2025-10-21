; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_months () (_ BitVec 32))
(declare-fun x_beta () (_ BitVec 32))
(assert
 (bvsle (_ bv4294966096 32) x_months))
(assert
 (bvsge (_ bv1199 32) x_months))
(assert
 (bvsle (_ bv0 32) x_beta))
(assert
 (let ((?x80467 (bvadd x_months (_ bv24003 32))))
 (let ((?x88832 (bvsub ?x80467 (bvmul (bvsdiv (bvsub ?x80467 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x1952 (ite (or (= ?x88832 (_ bv4 32)) (= ?x88832 (_ bv6 32)) (= ?x88832 (_ bv9 32)) (= ?x88832 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x77664 (and (= (bvsmod (bvsdiv (bvsub ?x80467 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x80467 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x50302 (ite (or $x77664 (= (bvsmod (bvsdiv (bvsub ?x80467 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x88832 (_ bv2 32)) ?x50302 ?x1952))))))))
(assert
 (let (($x49747 (bvsle (_ bv27 32) x_beta)))
 (let ((?x50007 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x82563 (= x_months ?x50007)))
 (or (bvsgt x_months ?x50007) (and $x82563 $x49747))))))
(assert
 (let ((?x80092 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
 (let (($x2028 (= x_months ?x80092)))
 (or (bvslt x_months ?x80092) (and $x2028 (bvsge (_ bv0 32) x_beta))))))
(assert
 (let ((?x50007 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x82563 (= x_months ?x50007)))
 (not (and $x82563 (= (_ bv27 32) x_beta))))))
(assert
 (let ((?x80092 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
(let (($x2028 (= x_months ?x80092)))
(not (and $x2028 (= (_ bv0 32) x_beta))))))
(check-sat)
