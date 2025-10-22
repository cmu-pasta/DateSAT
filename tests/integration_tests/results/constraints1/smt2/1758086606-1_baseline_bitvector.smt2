; benchmark generated from python API
(set-info :status unknown)
(declare-fun x_month () (_ BitVec 32))
(declare-fun x_year () (_ BitVec 32))
(declare-fun x_day () (_ BitVec 32))
(assert
 (let (($x1705 (or (= (_ bv4 32) x_month) (= (_ bv6 32) x_month) (= (_ bv9 32) x_month) (= (_ bv11 32) x_month))))
 (let (($x1843 (and (= (_ bv0 32) (bvsmod x_year (_ bv4 32))) (and (distinct (_ bv0 32) (bvsmod x_year (_ bv100 32))) true))))
 (let (($x1720 (= (_ bv2 32) x_month)))
 (let ((?x644 (ite $x1720 (ite (or $x1843 (= (_ bv0 32) (bvsmod x_year (_ bv400 32)))) (_ bv29 32) (_ bv28 32)) (ite $x1705 (_ bv30 32) (_ bv31 32)))))
 (let (($x3381 (bvsle x_day ?x644)))
 (let (($x756 (bvsle (_ bv1 32) x_day)))
 (let (($x3697 (bvsle (_ bv1 32) x_month)))
 (let (($x1022 (bvsge (_ bv12 32) x_month)))
 (let (($x1408 (bvsle (_ bv1901 32) x_year)))
 (or (and (= (_ bv1900 32) x_year) (bvsle (_ bv3 32) x_month) $x1022 $x756 $x3381) (and $x1408 (bvsge (_ bv2099 32) x_year) $x3697 $x1022 $x756 $x3381) (and (= (_ bv2100 32) x_year) $x3697 (bvsge (_ bv2 32) x_month) $x756 $x3381))))))))))))
(assert
 (let (($x1282 (or (bvslt (_ bv2 32) x_month) (and (= (_ bv2 32) x_month) (bvsle (_ bv28 32) x_day)))))
 (let (($x1385 (= (_ bv2000 32) x_year)))
 (or (bvslt (_ bv2000 32) x_year) (and $x1385 $x1282)))))
(assert
 (let (($x1386 (or (bvsgt (_ bv3 32) x_month) (and (= (_ bv3 32) x_month) (bvsge (_ bv1 32) x_day)))))
 (let (($x1385 (= (_ bv2000 32) x_year)))
 (or (bvsgt (_ bv2000 32) x_year) (and $x1385 $x1386)))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv2 32) x_month) (= (_ bv28 32) x_day))))
(assert
 (not (and (= (_ bv2000 32) x_year) (= (_ bv3 32) x_month) (= (_ bv1 32) x_day))))
(check-sat)
