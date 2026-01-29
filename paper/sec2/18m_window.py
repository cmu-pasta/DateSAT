import datetime
import importlib
import sys

sys.modules["_datetime"] = None
importlib.reload(datetime)

from datetime import date

from dateutil.relativedelta import relativedelta


def is_in_same_18m_window_1(base_date: date, event_date: date) -> bool:
    if event_date < base_date:
        return False

    elapsed_m = (event_date.year - base_date.year) * 12 + (
        event_date.month - base_date.month
    )
    if event_date.day < base_date.day:
        elapsed_m -= 1

    return elapsed_m < 18


def is_in_same_18m_window_2(base_date: date, event_date: date) -> bool:
    if event_date < base_date:
        return False

    window_end = base_date + relativedelta(months=18)
    return event_date < window_end


if __name__ == "__main__":
    # Sample test cases
    test_cases = [
        # (base_date, event_date, description)
        (date(2024, 1, 15), date(2024, 6, 15), "5 months later"),
        (date(2024, 1, 15), date(2025, 7, 14), "17 months, 29 days later"),
        (date(2024, 1, 15), date(2025, 7, 15), "exactly 18 months later"),
        (date(2024, 1, 15), date(2025, 7, 16), "18 months + 1 day later"),
        (date(2024, 1, 15), date(2023, 12, 1), "before base date"),
        (date(2024, 1, 31), date(2024, 2, 28), "end of month edge case"),
    ]

    print("Testing 18-month window functions\n")
    print(
        f"{'Base Date':<12} {'Event Date':<12} {'Description':<25} {'Method 1':<10} {'Method 2':<10} {'Match'}"
    )
    print("-" * 85)

    for base, event, desc in test_cases:
        result1 = is_in_same_18m_window_1(base, event)
        result2 = is_in_same_18m_window_2(base, event)
        match = "✓" if result1 == result2 else "✗"
        print(
            f"{str(base):<12} {str(event):<12} {desc:<25} {str(result1):<10} {str(result2):<10} {match}"
        )
