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
 (let ((?x27184 (bvadd x_months (_ bv24003 32))))
 (let ((?x35229 (bvsub ?x27184 (bvmul (bvsdiv (bvsub ?x27184 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x22558 (ite (or (= ?x35229 (_ bv4 32)) (= ?x35229 (_ bv6 32)) (= ?x35229 (_ bv9 32)) (= ?x35229 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x16168 (and (= (bvsmod (bvsdiv (bvsub ?x27184 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x27184 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x22470 (ite (or $x16168 (= (bvsmod (bvsdiv (bvsub ?x27184 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x35229 (_ bv2 32)) ?x22470 ?x22558))))))))
(assert
 (let (($x58392 (bvsle (_ bv27 32) x_beta)))
 (let ((?x81509 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x49568 (= x_months ?x81509)))
 (or (bvsgt x_months ?x81509) (and $x49568 $x58392))))))
(assert
 (let ((?x27989 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
 (let (($x18549 (= x_months ?x27989)))
 (or (bvslt x_months ?x27989) (and $x18549 (bvsge (_ bv0 32) x_beta))))))
(assert
 (let ((?x81509 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x49568 (= x_months ?x81509)))
 (not (and $x49568 (= (_ bv27 32) x_beta))))))
(assert
 (let ((?x27989 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
(let (($x18549 (= x_months ?x27989)))
(not (and $x18549 (= (_ bv0 32) x_beta))))))
(check-sat)
