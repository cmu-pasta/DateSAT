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
 (let ((?x34334 (bvadd x_months (_ bv24003 32))))
 (let ((?x72161 (bvsub ?x34334 (bvmul (bvsdiv (bvsub ?x34334 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x81867 (ite (or (= ?x72161 (_ bv4 32)) (= ?x72161 (_ bv6 32)) (= ?x72161 (_ bv9 32)) (= ?x72161 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x28687 (and (= (bvsmod (bvsdiv (bvsub ?x34334 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x34334 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x47210 (ite (or $x28687 (= (bvsmod (bvsdiv (bvsub ?x34334 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x72161 (_ bv2 32)) ?x47210 ?x81867))))))))
(assert
 (let (($x14875 (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) (bvsge (_ bv27 32) x_beta))))
 (let (($x29479 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) $x14875)))
 (not $x29479))))
(assert
 (let (($x69004 (bvsle (_ bv0 32) x_beta)))
(let (($x35032 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) $x69004))))
(not $x35032))))
(check-sat)
