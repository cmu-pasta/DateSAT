; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () (_ BitVec 32))
(declare-fun x_year () (_ BitVec 32))
(declare-fun x_day () (_ BitVec 32))
(assert
 (let (($x6965 (or (= (_ bv4 32) x_month) (= (_ bv6 32) x_month) (= (_ bv9 32) x_month) (= (_ bv11 32) x_month))))
 (let (($x3193 (and (= (_ bv0 32) (bvsmod x_year (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod x_year (_ bv100 32))) true))))
 (let (($x534 (= (_ bv2 32) x_month)))
 (let ((?x6626 (ite $x534 (ite (or $x3193 (= (_ bv0 32) (bvsmod x_year (_ bv400 32)))) (_ bv29 32) (_ bv28 32)) (ite $x6965 (_ bv30 32) (_ bv31 32)))))
 (let (($x4314 (bvsle x_day ?x6626)))
 (let (($x4007 (bvsle (_ bv1 32) x_day)))
 (let (($x1881 (bvsle (_ bv1 32) x_month)))
 (let (($x859 (bvsge (_ bv12 32) x_month)))
 (let (($x2442 (bvsle (_ bv1901 32) x_year)))
 (or (and (= (_ bv1900 32) x_year) (bvsle (_ bv3 32) x_month) $x859 $x4007 $x4314) (and $x2442 (bvsge (_ bv2099 32) x_year) $x1881 $x859 $x4007 $x4314) (and (= (_ bv2100 32) x_year) $x1881 (bvsge (_ bv2 32) x_month) $x4007 $x4314))))))))))))
(assert
 (let (($x3156 (or (bvslt (_ bv2 32) x_month) (and (= (_ bv2 32) x_month) (bvsle (_ bv28 32) x_day)))))
 (let (($x708 (= (_ bv2000 32) x_year)))
 (or (bvslt (_ bv2000 32) x_year) (and $x708 $x3156)))))
(assert
 (let (($x8138 (or (bvsgt (_ bv3 32) x_month) (and (= (_ bv3 32) x_month) (bvsge (_ bv1 32) x_day)))))
 (let (($x708 (= (_ bv2000 32) x_year)))
 (or (bvsgt (_ bv2000 32) x_year) (and $x708 $x8138)))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv2 32) x_month) (= (_ bv28 32) x_day))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv3 32) x_month) (= (_ bv1 32) x_day))))
(check-sat)
