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
 (let ((?x21889 (bvadd x_months (_ bv24003 32))))
 (let ((?x50651 (bvsub ?x21889 (bvmul (bvsdiv (bvsub ?x21889 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x80484 (ite (or (= ?x50651 (_ bv4 32)) (= ?x50651 (_ bv6 32)) (= ?x50651 (_ bv9 32)) (= ?x50651 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x2698 (and (= (bvsmod (bvsdiv (bvsub ?x21889 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x21889 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x49643 (ite (or $x2698 (= (bvsmod (bvsdiv (bvsub ?x21889 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x50651 (_ bv2 32)) ?x49643 ?x80484))))))))
(assert
 (let (($x48789 (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) (bvsge (_ bv27 32) x_beta))))
 (let (($x66878 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) $x48789)))
 (not $x66878))))
(assert
 (let (($x23186 (bvsle (_ bv0 32) x_beta)))
(let (($x46601 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) $x23186))))
(not $x46601))))
(check-sat)
