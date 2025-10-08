from datesmt.core import Date, Period
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_epoch_days import EpochDaysSolver
from datesmt.symbolic_hybrid import HybridDateSolver


def test_stepwise_two_months_from_jan_30_non_leap():
    """Verify Jan 30 + 1m + 1m (stepwise) semantics across solvers (non-leap 2023).

    This test only composes two Period(0,1,0) month additions stepwise. It does not
    use a single Period(0,2,0) addition. Expected result is March 28, 2023.
    """
    base = Date(2023, 1, 30)
    p1 = Period(0, 1, 0)

    # Baseline
    s = BaselineSolver()
    x = s.add_date_var("x")
    s.add_constraint(x == base)
    t1 = s.add_date_var("t1")
    s.add_constraint(t1 == x + p1)
    t2 = s.add_date_var("t2")
    s.add_constraint(t2 == t1 + p1)
    y = s.add_date_var("y")
    s.add_constraint(y == t2)
    res = s.solve()
    assert res["status"] == "sat"
    assert res["dates"]["y"] == Date(2023, 3, 28)

    # Epoch_days
    s2 = EpochDaysSolver()
    x = s2.add_date_var("x")
    s2.add_constraint(x == base)
    t1 = s2.add_date_var("t1")
    s2.add_constraint(t1 == x + p1)
    t2 = s2.add_date_var("t2")
    s2.add_constraint(t2 == t1 + p1)
    y = s2.add_date_var("y")
    s2.add_constraint(y == t2)
    res2 = s2.solve()
    assert res2["status"] == "sat"
    assert res2["dates"]["y"] == Date(2023, 3, 28)

    # Hybrid (default period addition semantics)
    sh = HybridDateSolver()
    x = sh.add_date_var("x")
    sh.add_constraint(x == base)
    t1 = sh.add_date_var("t1")
    sh.add_constraint(t1 == x + p1)
    t2 = sh.add_date_var("t2")
    sh.add_constraint(t2 == t1 + p1)
    y = sh.add_date_var("y")
    sh.add_constraint(y == t2)
    resh = sh.solve()
    assert resh["status"] == "sat"
    assert resh["dates"]["y"] == Date(2023, 3, 28)
