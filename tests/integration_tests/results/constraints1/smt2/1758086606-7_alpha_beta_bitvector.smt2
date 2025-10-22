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
 (let ((?x84512 (bvadd x_months (_ bv24003 32))))
 (let ((?x1148 (bvsub ?x84512 (bvmul (bvsdiv (bvsub ?x84512 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x84034 (ite (or (= (_ bv4 32) ?x1148) (= (_ bv6 32) ?x1148) (= (_ bv9 32) ?x1148) (= (_ bv11 32) ?x1148)) (_ bv30 32) (_ bv31 32))))
 (let (($x32545 (and (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x84512 (_ bv1 32)) (_ bv12 32)) (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x84512 (_ bv1 32)) (_ bv12 32)) (_ bv100 32))) true))))
 (let ((?x15646 (ite (or $x32545 (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x84512 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= (_ bv2 32) ?x1148) ?x15646 ?x84034))))))))
(assert
 (let (($x2828 (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) (bvsge (_ bv27 32) x_beta))))
 (let (($x84402 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) $x2828)))
 (not $x84402))))
(assert
 (let (($x15599 (bvsle (_ bv0 32) x_beta)))
(let (($x19699 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) $x15599))))
(not $x19699))))
(check-sat)
