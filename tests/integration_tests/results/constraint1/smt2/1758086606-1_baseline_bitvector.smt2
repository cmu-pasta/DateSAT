; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () (_ BitVec 32))
(declare-fun x_year () (_ BitVec 32))
(declare-fun x_day () (_ BitVec 32))
(assert
 (let (($x857 (or (= (_ bv4 32) x_month) (= (_ bv6 32) x_month) (= (_ bv9 32) x_month) (= (_ bv11 32) x_month))))
 (let (($x6482 (and (= (_ bv0 32) (bvsmod x_year (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod x_year (_ bv100 32))) true))))
 (let (($x1672 (= (_ bv2 32) x_month)))
 (let ((?x6726 (ite $x1672 (ite (or $x6482 (= (_ bv0 32) (bvsmod x_year (_ bv400 32)))) (_ bv29 32) (_ bv28 32)) (ite $x857 (_ bv30 32) (_ bv31 32)))))
 (let (($x2757 (bvsle x_day ?x6726)))
 (let (($x5091 (bvsle (_ bv1 32) x_day)))
 (let (($x3319 (bvsle (_ bv1 32) x_month)))
 (let (($x2985 (bvsge (_ bv12 32) x_month)))
 (let (($x3364 (bvsle (_ bv1901 32) x_year)))
 (or (and (= (_ bv1900 32) x_year) (bvsle (_ bv3 32) x_month) $x2985 $x5091 $x2757) (and $x3364 (bvsge (_ bv2099 32) x_year) $x3319 $x2985 $x5091 $x2757) (and (= (_ bv2100 32) x_year) $x3319 (bvsge (_ bv2 32) x_month) $x5091 $x2757))))))))))))
(assert
 (let (($x5072 (or (bvslt (_ bv2 32) x_month) (and (= (_ bv2 32) x_month) (bvsle (_ bv28 32) x_day)))))
 (let (($x3646 (= (_ bv2000 32) x_year)))
 (or (bvslt (_ bv2000 32) x_year) (and $x3646 $x5072)))))
(assert
 (let (($x2423 (or (bvsgt (_ bv3 32) x_month) (and (= (_ bv3 32) x_month) (bvsge (_ bv1 32) x_day)))))
 (let (($x3646 (= (_ bv2000 32) x_year)))
 (or (bvsgt (_ bv2000 32) x_year) (and $x3646 $x2423)))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv2 32) x_month) (= (_ bv28 32) x_day))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv3 32) x_month) (= (_ bv1 32) x_day))))
(check-sat)
