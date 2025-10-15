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
 (let ((?x54110 (bvadd x_months (_ bv24003 32))))
 (let ((?x83821 (bvsub ?x54110 (bvmul (bvsdiv (bvsub ?x54110 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x73325 (ite (or (= ?x83821 (_ bv4 32)) (= ?x83821 (_ bv6 32)) (= ?x83821 (_ bv9 32)) (= ?x83821 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x21922 (and (= (bvsmod (bvsdiv (bvsub ?x54110 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x54110 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x68229 (ite (or $x21922 (= (bvsmod (bvsdiv (bvsub ?x54110 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x83821 (_ bv2 32)) ?x68229 ?x73325))))))))
(assert
 (let (($x28406 (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) (bvsge (_ bv29 32) x_beta))))
 (let (($x21559 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv4 32)) (_ bv24003 32))) $x28406)))
 (not $x21559))))
(assert
 (let (($x83194 (bvsle (_ bv0 32) x_beta)))
(let (($x22382 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2023 32) (_ bv12 32)) (_ bv5 32)) (_ bv24003 32))) $x83194))))
(not $x22382))))
(check-sat)
