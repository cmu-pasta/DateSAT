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
 (let ((?x49170 (bvadd x_months (_ bv24003 32))))
 (let ((?x65299 (bvsub ?x49170 (bvmul (bvsdiv (bvsub ?x49170 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x51097 (ite (or (= ?x65299 (_ bv4 32)) (= ?x65299 (_ bv6 32)) (= ?x65299 (_ bv9 32)) (= ?x65299 (_ bv11 32))) (_ bv30 32) (_ bv31 32))))
 (let (($x60146 (and (= (bvsmod (bvsdiv (bvsub ?x49170 (_ bv1 32)) (_ bv12 32)) (_ bv4 32)) (_ bv0 32)) (and (distinct (bvsmod (bvsdiv (bvsub ?x49170 (_ bv1 32)) (_ bv12 32)) (_ bv100 32)) (_ bv0 32)) true))))
 (let ((?x41961 (ite (or $x60146 (= (bvsmod (bvsdiv (bvsub ?x49170 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)) (_ bv0 32))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= ?x65299 (_ bv2 32)) ?x41961 ?x51097))))))))
(assert
 (let (($x22544 (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) (bvsge (_ bv27 32) x_beta))))
 (let (($x82713 (or (bvslt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))) $x22544)))
 (not $x82713))))
(assert
 (let (($x19491 (bvsle (_ bv0 32) x_beta)))
(let (($x28348 (or (bvsgt x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) (and (= x_months (bvsub (bvadd (bvmul (_ bv2022 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))) $x19491))))
(not $x28348))))
(check-sat)
