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
 (let ((?x85020 (bvadd x_months (_ bv24003 32))))
 (let ((?x57767 (bvsub ?x85020 (bvmul (bvsdiv (bvsub ?x85020 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x64364 (ite (or (= ?x57767 (_ bv4 32)) (= ?x57767 (_ bv6 32)) (= ?x57767 (_ bv9 32)) (= ?x57767 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x66244 (and (= (bvsmod (bvsdiv (bvsub ?x85020 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x85020 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x39393 (ite (or $x66244 (= (bvsmod (bvsdiv (bvsub ?x85020 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x57767 (_ bv2 32)) ?x39393 ?x64364))))))))
(assert
 (let (($x14455 (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) (bvsge (_ bv29 32) x_beta))))
 (let (($x61254 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) $x14455)))
 (not $x61254))))
(assert
 (let (($x28462 (bvsle (_ bv0 32) x_beta)))
(let (($x13945 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) $x28462))))
(not $x13945))))
(check-sat)
