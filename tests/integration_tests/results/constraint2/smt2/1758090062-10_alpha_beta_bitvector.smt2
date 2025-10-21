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
 (let ((?x59997 (bvadd x_months (_ bv24003 32))))
 (let ((?x22963 (bvsub ?x59997 (bvmul (bvsdiv (bvsub ?x59997 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x90800 (ite (or (= ?x22963 (_ bv4 32)) (= ?x22963 (_ bv6 32)) (= ?x22963 (_ bv9 32)) (= ?x22963 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x34368 (and (= (bvsmod (bvsdiv (bvsub ?x59997 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x59997 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x43605 (ite (or $x34368 (= (bvsmod (bvsdiv (bvsub ?x59997 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x22963 (_ bv2 32)) ?x43605 ?x90800))))))))
(assert
 (let (($x16277 (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) (bvsge (_ bv29 32) x_beta))))
 (let (($x50994 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) $x16277)))
 (not $x50994))))
(assert
 (let (($x21474 (bvsle (_ bv0 32) x_beta)))
(let (($x4725 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) $x21474))))
(not $x4725))))
(check-sat)
