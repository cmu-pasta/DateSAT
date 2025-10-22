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
 (let ((?x81207 (bvadd x_months (_ bv24003 32))))
 (let ((?x2234 (bvsub ?x81207 (bvmul (bvsdiv (bvsub ?x81207 (_ bv1 32)) (_ bv12 32)) (_ bv12 32)))))
 (let ((?x410 (ite (or (= (_ bv4 32) ?x2234) (= (_ bv6 32) ?x2234) (= (_ bv9 32) ?x2234) (= (_ bv11 32) ?x2234)) (_ bv30 32) (_ bv31 32))))
 (let (($x2985 (and (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x81207 (_ bv1 32)) (_ bv12 32)) (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x81207 (_ bv1 32)) (_ bv12 32)) (_ bv100 32))) true))))
 (let ((?x3527 (ite (or $x2985 (= (_ bv0 32) (bvsmod (bvsdiv (bvsub ?x81207 (_ bv1 32)) (_ bv12 32)) (_ bv400 32)))) (_ bv29 32) (_ bv28 32))))
 (bvslt x_beta (ite (= (_ bv2 32) ?x2234) ?x3527 ?x410))))))))
(assert
 (let (($x49016 (bvsle (_ bv27 32) x_beta)))
 (let ((?x82599 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x2914 (= x_months ?x82599)))
 (or (bvsgt x_months ?x82599) (and $x2914 $x49016))))))
(assert
 (let ((?x29370 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
 (let (($x3193 (= x_months ?x29370)))
 (or (bvslt x_months ?x29370) (and $x3193 (bvsge (_ bv0 32) x_beta))))))
(assert
 (let ((?x82599 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv2 32)) (_ bv24003 32))))
 (let (($x2914 (= x_months ?x82599)))
 (not (and $x2914 (= (_ bv27 32) x_beta))))))
(assert
 (let ((?x29370 (bvsub (bvadd (bvmul (_ bv2000 32) (_ bv12 32)) (_ bv3 32)) (_ bv24003 32))))
(let (($x3193 (= x_months ?x29370)))
(not (and $x3193 (= (_ bv0 32) x_beta))))))
(check-sat)
