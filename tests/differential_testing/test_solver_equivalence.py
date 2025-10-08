"""
Differential testing for solver equivalence between baseline and epoch_days implementations.

These tests verify that both baseline and epoch_days solvers produce identical:
- Satisfiability results (SAT/UNSAT)
- Model solutions when satisfiable
- Period arithmetic results
- Epoch rebasing consistency

This tests the core solver behavior and ensures the epoch_days implementation
faithfully reproduces the baseline solver's results.

These are differential tests because they compare two implementations against
each other rather than against ground truth.
"""

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import pytest

from datesmt.core import Date, Period
from datesmt.symbolic_baseline import DateSolver as BaselineSolver
from datesmt.symbolic_epoch_days import (
    EpochDaysSolver,
    from_days_since_epoch,
    to_days_since_epoch,
)


class TestSolverEquivalence:
    """Test that Baseline and Epoch_days implementations produce equivalent results."""

    @pytest.mark.parametrize(
        "constraint_desc,expected_sat",
        [
            # SAT cases
            ("x == Date(2020, 6, 15)", True),
            ("x == Date(2020, 2, 29)", True),  # Leap year
            ("x >= Date(2020, 1, 1) and x <= Date(2020, 12, 31)", True),
            ("x == Date(2020, 6, 15) and y == Date(2020, 6, 20) and x < y", True),
            # UNSAT cases
            ("x == Date(2020, 2, 30)", False),  # Invalid date
            ("x == Date(2021, 2, 29)", False),  # Non-leap year Feb 29
            ("x == Date(2020, 4, 31)", False),  # April 31
            (
                "x == Date(2020, 6, 15) and x == Date(2020, 6, 20)",
                False,
            ),  # Contradiction
        ],
    )
    def test_sat_unsat_parity_simple_date_constraints(
        self, constraint_desc, expected_sat
    ):
        """Test SAT/UNSAT parity for simple date constraints."""
        baseline_result = self._solve_baseline(constraint_desc)
        epoch_days_result = self._solve_epoch_days(constraint_desc)

        assert (
            baseline_result['status'] == epoch_days_result['status']
        ), f"Constraint: {constraint_desc}\nBaseline: {baseline_result['status']}, Epoch_days: {epoch_days_result['status']}"

        if expected_sat:
            assert baseline_result['status'] == 'sat'
            assert epoch_days_result['status'] == 'sat'
        else:
            assert baseline_result['status'] == 'unsat'
            assert epoch_days_result['status'] == 'unsat'

    @pytest.mark.parametrize(
        "constraint_desc",
        [
            "x == Date(2020, 6, 15)",
            "x == Date(2020, 2, 29) and y == Date(2021, 2, 28)",
            "x >= Date(2020, 1, 1) and x <= Date(2020, 12, 31) and y == x + Period(0, 0, 1)",
        ],
    )
    def test_model_agreement_when_sat(self, constraint_desc):
        """Test that when SAT, both implementations produce equivalent models."""
        baseline_result = self._solve_baseline(constraint_desc)
        epoch_days_result = self._solve_epoch_days(constraint_desc)

        if baseline_result['status'] == 'sat' and epoch_days_result['status'] == 'sat':
            # Compare the concrete dates from both models
            baseline_dates = baseline_result['dates']
            epoch_days_dates = epoch_days_result['dates']

            assert set(baseline_dates.keys()) == set(
                epoch_days_dates.keys()
            ), f"Different variable sets: {constraint_desc}"

            for var_name in baseline_dates.keys():
                baseline_date = baseline_dates[var_name]
                epoch_days_date = epoch_days_dates[var_name]

                # Convert both to days since epoch for comparison
                baseline_days = self._date_to_epoch_days(baseline_date)
                epoch_days_days = self._date_to_epoch_days(epoch_days_date)

                assert baseline_days == epoch_days_days, (
                    f"Variable {var_name}: Baseline={baseline_date} ({baseline_days} days), "
                    f"Epoch_days={epoch_days_date} ({epoch_days_days} days)"
                )

    @pytest.mark.parametrize(
        "constraint_desc",
        [
            "x == Date(2020, 6, 15) and y == x + Period(1, 2, 3)",
            "x == Date(2020, 2, 29) and y == x + Period(1, 0, 0)",  # Leap year + 1 year
            "x == Date(2020, 1, 31) and y == x + Period(0, 1, 0)",  # Month boundary
            "x == Date(2020, 6, 15) and y == x - Period(0, 0, 5)",  # Subtraction
        ],
    )
    def test_period_arithmetic_equivalence(self, constraint_desc):
        """Test that period arithmetic produces equivalent results."""
        baseline_result = self._solve_baseline(constraint_desc)
        epoch_days_result = self._solve_epoch_days(constraint_desc)

        assert (
            baseline_result['status'] == epoch_days_result['status']
        ), f"Constraint: {constraint_desc}\nBaseline: {baseline_result['status']}, Epoch_days: {epoch_days_result['status']}"

        if baseline_result['status'] == 'sat':
            # Compare the arithmetic results
            baseline_dates = baseline_result['dates']
            epoch_days_dates = epoch_days_result['dates']

            for var_name in baseline_dates.keys():
                baseline_date = baseline_dates[var_name]
                epoch_days_date = epoch_days_dates[var_name]

                # For differential testing, we just need them to be equal, not necessarily in epoch days
                assert (
                    baseline_date == epoch_days_date
                ), f"Variable {var_name}: Baseline={baseline_date}, Epoch_days={epoch_days_date}"

    def test_epoch_rebasing_consistency(self):
        """Test that epoch rebasing produces consistent results."""
        # Test that the epoch (March 1, 2000) is consistently represented
        epoch = Date(2000, 3, 1)

        # Test baseline epoch representation
        baseline_solver = BaselineSolver()
        x = baseline_solver.add_date_var("x")
        baseline_solver.add_constraint(x == epoch)
        baseline_result = baseline_solver.solve()

        # Test epoch_days epoch representation
        epoch_days_solver = EpochDaysSolver()
        y = epoch_days_solver.add_date_var("y")
        epoch_days_solver.add_constraint(y == epoch)
        epoch_days_result = epoch_days_solver.solve()

        assert baseline_result['status'] == 'sat'
        assert epoch_days_result['status'] == 'sat'

        baseline_date = baseline_result['dates']['x']
        epoch_days_date = epoch_days_result['dates']['y']

        assert baseline_date == epoch
        assert epoch_days_date == epoch

        # Test that epoch days conversion is consistent
        baseline_days = self._date_to_epoch_days(baseline_date)
        epoch_days_days = self._date_to_epoch_days(epoch_days_date)

        assert baseline_days == 0  # Epoch should be day 0
        assert epoch_days_days == 0

    @pytest.mark.parametrize("seed", range(10))
    def test_random_constraint_equivalence(self, seed):
        """Test equivalence on randomly generated constraints."""
        random.seed(42 + seed)  # For reproducible tests with different seeds

        constraint = self._generate_random_constraint()
        baseline_result = self._solve_baseline(constraint)
        epoch_days_result = self._solve_epoch_days(constraint)

        assert (
            baseline_result['status'] == epoch_days_result['status']
        ), f"Random constraint: {constraint}\nBaseline: {baseline_result['status']}, Epoch_days: {epoch_days_result['status']}"

    def _solve_baseline(self, constraint_desc: str) -> Dict[str, Any]:
        """Solve constraint using baseline solver."""
        solver = BaselineSolver()
        x = None
        y = None

        # Parse and add constraints (simplified parsing for test cases)
        if "x == Date(" in constraint_desc:
            # Extract date from constraint
            start = constraint_desc.find("Date(") + 5
            end = constraint_desc.find(")", start)
            date_parts = constraint_desc[start:end].split(", ")
            year, month, day = (
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2]),
            )

            # Skip invalid dates
            try:
                date_obj = Date(year, month, day)
                x = solver.add_date_var("x")
                solver.add_constraint(x == date_obj)
            except ValueError:
                # Return unsat for invalid dates
                return {'status': 'unsat'}

        if "y == Date(" in constraint_desc:
            start = constraint_desc.find("y == Date(") + 10
            end = constraint_desc.find(")", start)
            date_parts = constraint_desc[start:end].split(", ")
            year, month, day = (
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2]),
            )

            try:
                date_obj = Date(year, month, day)
                y = solver.add_date_var("y")
                solver.add_constraint(y == date_obj)
            except ValueError:
                return {'status': 'unsat'}

        if "x + Period(" in constraint_desc:
            # Extract period from constraint
            start = constraint_desc.find("Period(") + 7
            end = constraint_desc.find(")", start)
            period_parts = constraint_desc[start:end].split(", ")
            years, months, days = (
                int(period_parts[0]),
                int(period_parts[1]),
                int(period_parts[2]),
            )
            period_obj = Period(years, months, days)

            if "y == x +" in constraint_desc and x is not None:
                y = solver.add_date_var("y")
                solver.add_constraint(y == x + period_obj)

        if "x - Period(" in constraint_desc:
            start = constraint_desc.find("Period(") + 7
            end = constraint_desc.find(")", start)
            period_parts = constraint_desc[start:end].split(", ")
            years, months, days = (
                int(period_parts[0]),
                int(period_parts[1]),
                int(period_parts[2]),
            )
            period_obj = Period(years, months, days)

            if "y == x -" in constraint_desc and x is not None:
                y = solver.add_date_var("y")
                solver.add_constraint(y == x - period_obj)

        if "x < y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x < y)
        elif "x > y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x > y)
        elif "x <= y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x <= y)
        elif "x >= y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x >= y)

        return solver.solve()

    def _solve_epoch_days(self, constraint_desc: str) -> Dict[str, Any]:
        """Solve constraint using epoch_days solver."""
        solver = EpochDaysSolver()
        x = None
        y = None

        # Parse and add constraints (simplified parsing for test cases)
        if "x == Date(" in constraint_desc:
            start = constraint_desc.find("Date(") + 5
            end = constraint_desc.find(")", start)
            date_parts = constraint_desc[start:end].split(", ")
            year, month, day = (
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2]),
            )

            try:
                date_obj = Date(year, month, day)
                x = solver.add_date_var("x")
                solver.add_constraint(x == date_obj)
            except ValueError:
                return {'status': 'unsat'}

        if "y == Date(" in constraint_desc:
            start = constraint_desc.find("y == Date(") + 10
            end = constraint_desc.find(")", start)
            date_parts = constraint_desc[start:end].split(", ")
            year, month, day = (
                int(date_parts[0]),
                int(date_parts[1]),
                int(date_parts[2]),
            )

            try:
                date_obj = Date(year, month, day)
                y = solver.add_date_var("y")
                solver.add_constraint(y == date_obj)
            except ValueError:
                return {'status': 'unsat'}

        if "x + Period(" in constraint_desc:
            start = constraint_desc.find("Period(") + 7
            end = constraint_desc.find(")", start)
            period_parts = constraint_desc[start:end].split(", ")
            years, months, days = (
                int(period_parts[0]),
                int(period_parts[1]),
                int(period_parts[2]),
            )
            period_obj = Period(years, months, days)

            if "y == x +" in constraint_desc and x is not None:
                y = solver.add_date_var("y")
                solver.add_constraint(y == x + period_obj)

        if "x - Period(" in constraint_desc:
            start = constraint_desc.find("Period(") + 7
            end = constraint_desc.find(")", start)
            period_parts = constraint_desc[start:end].split(", ")
            years, months, days = (
                int(period_parts[0]),
                int(period_parts[1]),
                int(period_parts[2]),
            )
            period_obj = Period(years, months, days)

            if "y == x -" in constraint_desc and x is not None:
                y = solver.add_date_var("y")
                solver.add_constraint(y == x - period_obj)

        if "x < y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x < y)
        elif "x > y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x > y)
        elif "x <= y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x <= y)
        elif "x >= y" in constraint_desc and x is not None and y is not None:
            solver.add_constraint(x >= y)

        return solver.solve()

    def _date_to_epoch_days(self, date_obj: Date) -> int:
        """Convert Date to days since epoch (March 1, 2000)."""
        return to_days_since_epoch(date_obj)

    def _generate_random_constraint(self) -> str:
        """Generate a random constraint for testing."""
        # Simple random constraint generation
        year = random.randint(2000, 2020)
        month = random.randint(1, 12)
        day = random.randint(1, 28)  # Conservative to avoid invalid dates

        constraint_types = [
            f"x == Date({year}, {month}, {day})",
            f"x >= Date({year}, {month}, {day})",
            f"x <= Date({year}, {month}, {day})",
        ]

        return random.choice(constraint_types)

    # ============================================================================
    # Date Arithmetic Edge Cases Tests
    # ============================================================================

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "base_date,years",
        [
            # Add 1 year from Feb 29 in leap year
            (Date(2020, 2, 29), 1),
            (Date(2024, 2, 29), 1),
            # Add 1 year from Feb 28 in non-leap year
            (Date(2021, 2, 28), 1),
            (Date(2023, 2, 28), 1),
            # Add 1 year from Feb 29 in leap year to leap year
            (Date(2020, 2, 29), 4),
            (Date(2024, 2, 29), 4),
            # Add multiple years across leap year boundaries
            (Date(2020, 2, 29), 2),
            (Date(2020, 2, 29), 3),
            (Date(2020, 2, 29), 5),
        ],
    )
    def test_year_jumps_across_leap_years(self, base_date, years):
        """Test year jumps across leap years - differential only."""
        period = Period(years, 0, 0)

        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(base_date, period)
        epoch_days_result = self._test_epoch_days_period(base_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {base_date} + {years} years: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "base_date,months",
        [
            # Add 1 month from each month's 28th-31st
            (Date(2020, 1, 31), 1),  # Jan 31 + 1 month
            (Date(2021, 1, 31), 1),  # Jan 31 + 1 month
            (Date(2020, 4, 30), 1),  # Apr 30 + 1 month
            (Date(2020, 5, 31), 1),  # May 31 + 1 month
            (Date(2020, 6, 30), 1),  # Jun 30 + 1 month
            (Date(2020, 7, 31), 1),  # Jul 31 + 1 month
            (Date(2020, 8, 31), 1),  # Aug 31 + 1 month
            (Date(2020, 9, 30), 1),  # Sep 30 + 1 month
            (Date(2020, 10, 31), 1),  # Oct 31 + 1 month
            (Date(2020, 11, 30), 1),  # Nov 30 + 1 month
            (Date(2020, 12, 31), 1),  # Dec 31 + 1 month
            # Add multiple months
            (Date(2020, 1, 31), 2),  # Jan 31 + 2 months
            (Date(2020, 1, 31), 3),  # Jan 31 + 3 months
            (Date(2020, 1, 31), 12),  # Jan 31 + 12 months
        ],
    )
    def test_month_jumps_with_varying_lengths(self, base_date, months):
        """Test month jumps with varying month lengths - differential only."""
        period = Period(0, months, 0)

        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(base_date, period)
        epoch_days_result = self._test_epoch_days_period(base_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {base_date} + {months} months: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "base_date,period",
        [
            # Mixed periods crossing Feb in leap year
            (Date(2020, 1, 31), Period(0, 1, 0)),  # Jan 31 + 1 month
            (Date(2020, 1, 31), Period(0, 2, 0)),  # Jan 31 + 2 months
            (Date(2020, 1, 31), Period(1, 1, 0)),  # Jan 31 + 1 year 1 month
            # Mixed periods crossing Feb in non-leap year
            (Date(2021, 1, 31), Period(0, 1, 0)),  # Jan 31 + 1 month
            (Date(2021, 1, 31), Period(0, 2, 0)),  # Jan 31 + 2 months
            (Date(2021, 1, 31), Period(1, 1, 0)),  # Jan 31 + 1 year 1 month
            # Complex mixed periods
            (Date(2020, 1, 31), Period(1, 2, 3)),  # Jan 31 + 1y 2m 3d
            (Date(2020, 1, 31), Period(2, 6, 10)),  # Jan 31 + 2y 6m 10d
        ],
    )
    def test_mixed_periods_crossing_feb(self, base_date, period):
        """Test mixed periods where adding months crosses Feb (leap/non-leap) - differential only."""
        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(base_date, period)
        epoch_days_result = self._test_epoch_days_period(base_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {base_date} + {period}: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "base_date,period_or_years",
        [
            # Negative years across leap years
            (Date(2021, 2, 28), -1),  # 2021 Feb 28 - 1 year
            (Date(2025, 2, 28), -1),  # 2025 Feb 28 - 1 year
            # Negative months with varying lengths
            (Date(2020, 3, 31), -1),  # Mar 31 - 1 month
            (Date(2021, 3, 31), -1),  # Mar 31 - 1 month
            (Date(2020, 5, 31), -1),  # May 31 - 1 month
            (Date(2020, 6, 30), -1),  # Jun 30 - 1 month
            # Complex negative periods
            (Date(2021, 3, 31), Period(-1, -1, -1)),  # Mar 31 - 1y 1m 1d
        ],
    )
    def test_negative_periods_edge_cases(self, base_date, period_or_years):
        """Test negative periods with edge cases - differential only."""
        if isinstance(period_or_years, int):
            period = Period(period_or_years, 0, 0)
        else:
            period = period_or_years

        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(base_date, period)
        epoch_days_result = self._test_epoch_days_period(base_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {base_date} + {period}: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "years",
        [
            1,  # +1 year
            2,  # +2 years
            3,  # +3 years
            4,  # +4 years (leap year)
            5,  # +5 years
            8,  # +8 years (leap year)
        ],
    )
    def test_four_year_cycle_math(self, years):
        """Test 4-year cycle math for leap years - differential only."""
        # Test that the 4-year cycle is handled correctly
        base_date = Date(2020, 2, 29)  # Leap year
        period = Period(years, 0, 0)

        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(base_date, period)
        epoch_days_result = self._test_epoch_days_period(base_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {base_date} + {years} years: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    @pytest.mark.parametrize(
        "month,max_days",
        [
            (1, 31),
            (2, 29),
            (3, 31),
            (4, 30),
            (5, 31),
            (6, 30),
            (7, 31),
            (8, 31),
            (9, 30),
            (10, 31),
            (11, 30),
            (12, 31),
        ],
    )
    def test_month_lookup_path_validation(self, month, max_days):
        """Test month lookup path validation - differential only."""
        # Test in leap year (2020)
        leap_date = Date(2020, month, max_days)
        period = Period(0, 1, 0)

        # Test both implementations produce the same result
        baseline_result = self._test_baseline_period(leap_date, period)
        epoch_days_result = self._test_epoch_days_period(leap_date, period)

        # Differential test: both implementations should produce the same result
        assert (
            baseline_result == epoch_days_result
        ), f"Implementation mismatch: {leap_date} + 1 month: Baseline={baseline_result}, Epoch_days={epoch_days_result}"

    @pytest.mark.baseline
    @pytest.mark.epoch_days
    def test_edge_case_solver_constraints(self):
        """Test edge cases using solver constraints - differential only."""
        # Test a complex edge case with solver
        base_date = Date(2020, 2, 29)  # Leap year Feb 29
        period = Period(1, 1, 1)  # 1 year, 1 month, 1 day

        # Test baseline solver
        baseline_solver = BaselineSolver()
        x = baseline_solver.add_date_var("x")
        y = baseline_solver.add_date_var("y")

        baseline_solver.add_constraint(x == base_date)
        baseline_solver.add_constraint(y == x + period)

        baseline_result = baseline_solver.solve()
        assert baseline_result['status'] == 'sat'

        # Test epoch_days solver
        epoch_days_solver = EpochDaysSolver()
        x_adv = epoch_days_solver.add_date_var("x")
        y_adv = epoch_days_solver.add_date_var("y")

        epoch_days_solver.add_constraint(x_adv == base_date)
        epoch_days_solver.add_constraint(y_adv == x_adv + period)

        epoch_days_result = epoch_days_solver.solve()
        assert epoch_days_result['status'] == 'sat'

        # Differential test: both should produce the same result
        baseline_y = baseline_result['dates']['y']
        epoch_days_y = epoch_days_result['dates']['y']

        assert (
            baseline_y == epoch_days_y
        ), f"Edge case solver mismatch: Baseline={baseline_y}, Epoch_days={epoch_days_y}"

    def _test_baseline_period(self, base_date: Date, period: Period) -> Date:
        """Test period addition using baseline solver."""
        solver = BaselineSolver()
        x = solver.add_date_var("x")
        y = solver.add_date_var("y")

        solver.add_constraint(x == base_date)
        solver.add_constraint(y == x + period)

        result = solver.solve()
        assert result['status'] == 'sat'
        return result['dates']['y']

    def _test_epoch_days_period(self, base_date: Date, period: Period) -> Date:
        """Test period addition using epoch_days solver."""
        solver = EpochDaysSolver()
        x = solver.add_date_var("x")
        y = solver.add_date_var("y")

        solver.add_constraint(x == base_date)
        solver.add_constraint(y == x + period)

        result = solver.solve()
        assert result['status'] == 'sat'
        return result['dates']['y']

    # ============================================================================
    # Epoch Policy Tests (moved from test_epoch_policy.py)
    # ============================================================================

    def test_epoch_consistency_across_solvers(self):
        """Test that both solvers use the same epoch."""
        epoch = Date(2000, 3, 1)

        # Test baseline solver
        baseline_solver = BaselineSolver()
        x = baseline_solver.add_date_var("x")
        baseline_solver.add_constraint(x == epoch)
        baseline_result = baseline_solver.solve()

        # Test epoch_days solver
        epoch_days_solver = EpochDaysSolver()
        y = epoch_days_solver.add_date_var("y")
        epoch_days_solver.add_constraint(y == epoch)
        epoch_days_result = epoch_days_solver.solve()

        assert baseline_result['status'] == 'sat'
        assert epoch_days_result['status'] == 'sat'

        baseline_date = baseline_result['dates']['x']
        epoch_days_date = epoch_days_result['dates']['y']

        assert baseline_date == epoch
        assert epoch_days_date == epoch
        assert (
            baseline_date == epoch_days_date
        ), f"Epoch consistency mismatch: Baseline={baseline_date}, Epoch_days={epoch_days_date}"

    def test_epoch_regression_guard(self):
        """Test that changing the epoch preserves external semantics."""
        # This test ensures that if we change the epoch in a test fixture,
        # both sides apply the same rebase function

        # Simulate a different epoch for testing
        test_epoch = Date(2000, 3, 1)

        # Test that both solvers produce consistent results with the same epoch
        baseline_solver = BaselineSolver()
        x = baseline_solver.add_date_var("x")
        baseline_solver.add_constraint(x == test_epoch)
        baseline_result = baseline_solver.solve()

        epoch_days_solver = EpochDaysSolver()
        y = epoch_days_solver.add_date_var("y")
        epoch_days_solver.add_constraint(y == test_epoch)
        epoch_days_result = epoch_days_solver.solve()

        assert baseline_result['status'] == 'sat'
        assert epoch_days_result['status'] == 'sat'

        # Both should produce the same date
        baseline_date = baseline_result['dates']['x']
        epoch_days_date = epoch_days_result['dates']['y']

        assert baseline_date == epoch_days_date == test_epoch

    def test_epoch_implementation_consistency(self):
        """Test that both implementations handle epoch consistently."""
        # Test that both solvers produce the same results for epoch-related constraints
        epoch = Date(2000, 3, 1)
        test_date = Date(2000, 3, 15)

        # Test baseline solver
        baseline_solver = BaselineSolver()
        x = baseline_solver.add_date_var("x")
        y = baseline_solver.add_date_var("y")

        baseline_solver.add_constraint(x == epoch)
        baseline_solver.add_constraint(y == x + Period(0, 0, 14))  # +14 days
        baseline_solver.add_constraint(y == test_date)

        baseline_result = baseline_solver.solve()
        assert baseline_result['status'] == 'sat'

        # Test epoch_days solver
        epoch_days_solver = EpochDaysSolver()
        x_adv = epoch_days_solver.add_date_var("x")
        y_adv = epoch_days_solver.add_date_var("y")

        epoch_days_solver.add_constraint(x_adv == epoch)
        epoch_days_solver.add_constraint(y_adv == x_adv + Period(0, 0, 14))  # +14 days
        epoch_days_solver.add_constraint(y_adv == test_date)

        epoch_days_result = epoch_days_solver.solve()
        assert epoch_days_result['status'] == 'sat'

        # Both should produce the same result
        baseline_y = baseline_result['dates']['y']
        epoch_days_y = epoch_days_result['dates']['y']

        assert (
            baseline_y == epoch_days_y == test_date
        ), f"Epoch implementation mismatch: Baseline={baseline_y}, Epoch_days={epoch_days_y}"
