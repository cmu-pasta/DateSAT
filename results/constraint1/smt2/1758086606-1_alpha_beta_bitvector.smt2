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
 (let ((?x20840 (bvadd x_months (_ bv24003 32))))
 (let ((?x77808 (bvsub ?x20840 (bvmul (bvsdiv (bvsub ?x20840 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x73777 (ite (or (= ?x77808 (_ bv4 32)) (= ?x77808 (_ bv6 32)) (= ?x77808 (_ bv9 32)) (= ?x77808 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x36390 (and (= (bvsmod (bvsdiv (bvsub ?x20840 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x20840 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x14360 (ite (or $x36390 (= (bvsmod (bvsdiv (bvsub ?x20840 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x77808 (_ bv2 32)) ?x14360 ?x73777))))))))
(assert
 (let (($x73587 (bvsle (_ bv27 32) x_beta)))
 (let ((?x81199 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x73704 (= x_months ?x81199)))
 (or (bvsgt x_months ?x81199) (and $x73704 $x73587))))))
(assert
 (let ((?x82351 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
 (let (($x23616 (= x_months ?x82351)))
 (or (bvslt x_months ?x82351) (and $x23616 (bvsge (_ bv0 32) x_beta))))))
(assert
 (let ((?x81199 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x73704 (= x_months ?x81199)))
 (not (and $x73704 (= (_ bv27 32) x_beta))))))
(assert
 (let ((?x82351 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
(let (($x23616 (= x_months ?x82351)))
(not (and $x23616 (= (_ bv0 32) x_beta))))))
(check-sat)
