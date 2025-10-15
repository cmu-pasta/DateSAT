; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () (_ BitVec 32))
(declare-fun x_year () (_ BitVec 32))
(declare-fun x_day () (_ BitVec 32))
(assert
 (let (($x1159 (or (= (_ bv4 32) x_month) (= (_ bv6 32) x_month) (= (_ bv9 32) x_month) (= (_ bv11 32) x_month))))
 (let (($x3897 (and (= (_ bv0 32) (bvsmod x_year (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod x_year (_ bv100 32))) true))))
 (let (($x4710 (= (_ bv2 32) x_month)))
 (let ((?x4053 (ite $x4710 (ite (or $x3897 (= (_ bv0 32) (bvsmod x_year (_ bv400 32)))) (_ bv29 32) (_ bv28 32)) (ite $x1159 (_ bv30 32) (_ bv31 32)))))
 (let (($x900 (bvsle x_day ?x4053)))
 (let (($x3189 (bvsle (_ bv1 32) x_day)))
 (let (($x3741 (bvsle (_ bv1 32) x_month)))
 (let (($x2230 (bvsge (_ bv12 32) x_month)))
 (let (($x4642 (bvsle (_ bv1901 32) x_year)))
 (or (and (= (_ bv1900 32) x_year) (bvsle (_ bv3 32) x_month) $x2230 $x3189 $x900) (and $x4642 (bvsge (_ bv2099 32) x_year) $x3741 $x2230 $x3189 $x900) (and (= (_ bv2100 32) x_year) $x3741 (bvsge (_ bv2 32) x_month) $x3189 $x900))))))))))))
(assert
 (let (($x2842 (or (bvslt (_ bv2 32) x_month) (and (= (_ bv2 32) x_month) (bvsle (_ bv28 32) x_day)))))
 (let (($x4058 (= (_ bv2000 32) x_year)))
 (or (bvslt (_ bv2000 32) x_year) (and $x4058 $x2842)))))
(assert
 (let (($x5891 (or (bvsgt (_ bv3 32) x_month) (and (= (_ bv3 32) x_month) (bvsge (_ bv1 32) x_day)))))
 (let (($x4058 (= (_ bv2000 32) x_year)))
 (or (bvsgt (_ bv2000 32) x_year) (and $x4058 $x5891)))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv2 32) x_month) (= (_ bv28 32) x_day))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv3 32) x_month) (= (_ bv1 32) x_day))))
(check-sat)
