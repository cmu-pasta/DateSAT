"""
Concrete Python port of the Verus reference semantics (simple_date.rs), kept
deliberately literal: add_days follows the four recursive rules of
SimpleDate::add_days (written as a loop), not a faster closed form. Uses
floor division, which equals Verus' Euclidean division for the positive
divisors involved.
"""


def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def dim(y, m):
    return [31, 29 if leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def is_valid(date):
    y, m, d = date
    return 1 <= m <= 12 and 1 <= d <= dim(y, m)


def add_months(date, n):
    y, m, d = date
    y_ = y + (m - 1 + n) // 12
    m_ = 1 + (m - 1 + n) % 12
    return (y_, m_, min(d, dim(y_, m_)))


def add_days(date, n):
    assert is_valid(date)
    y, m, d = date
    while True:
        if 1 <= d + n <= dim(y, m):                     # ADD-DAYS
            return (y, m, d + n)
        if d + n > dim(y, m):                           # ADD-DAYS-OVER
            n = n - (dim(y, m) - d) - 1
            y, m, d = add_months((y, m, 1), 1)
        elif d > 1:                                     # ADD-DAYS-UNDER1
            n = d - 1 + n
            d = 1
        else:                                           # ADD-DAYS-UNDER2
            y_, m_, _ = add_months((y, m, d), -1)
            n = n + dim(y_, m_)
            y, m, d = y_, m_, 1


def add_period(date, period):
    years, months, days = period
    return add_days(add_months(date, years * 12 + months), days)


def lt(a, b):
    return a < b  # tuples compare lexicographically, as SimpleDate::lt
