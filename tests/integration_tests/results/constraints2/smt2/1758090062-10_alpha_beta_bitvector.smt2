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
 (let ((?x4736 (bvadd x_months (_ bv24003 32))))
 (let ((?x87918 (bvsub ?x4736 (bvmul (bvsdiv (bvsub ?x4736 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x68680 (ite (or (= (_ bv4 32) ?x87918) (= (_ bv6 32) ?x87918) (= (_ bv9 32) ?x87918) (= (_ bv11 32) ?x87918)) (_ bv30 32) (_ bv31 32))))
 (let (($x581 (and (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x4736 (_ bv1 32)) (_ bv12 32)) (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x4736 (_ bv1 32)) (_ bv12 32)) (_ bv100 32))) true))))
 (let ((?x8872 (ite (or $x581 (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x4736 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= (_ bv2 32) ?x87918) ?x8872 ?x68680))))))))
(assert
 (let (($x22926 (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) (bvsge (_ bv29 32) x_beta))))
 (let (($x32255 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) $x22926)))
 (not $x32255))))
(assert
 (let (($x1932 (bvsle (_ bv0 32) x_beta)))
(let (($x74989 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) $x1932))))
(not $x74989))))
(check-sat)
