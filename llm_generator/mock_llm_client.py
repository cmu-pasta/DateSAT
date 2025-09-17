"""
Mock LLM client for testing without OpenAI API.
Generates constraints that match the enhanced schema with coverage tags.
"""

import json
import random
try:
    from .id_counter import get_next_id
except ImportError:
    from id_counter import get_next_id


class MockLLMClient:
    """Mock LLM client that generates sample constraints with coverage tags."""

    def __init__(self):
        self.constraint_templates = [
            {
                "id": "constraint_{}",
                "description": "Simple date range constraint",
                "constraint_code": "x = builder.add_date_var('x')\nbuilder.add_constraint(x >= Date(2023, 1, 1), 'x >= 2023-01-01')\nbuilder.add_constraint(x <= Date(2023, 12, 31), 'x <= 2023-12-31')",
                "variables": ["x"],
                "coverage_tags": ["ineq_window"],
                "expected_satisfiable": True,
            },
            {
                "id": "constraint_{}",
                "description": "Leap year boundary test",
                "constraint_code": "x = builder.add_date_var('x')\nbuilder.add_constraint(x >= Date(2024, 2, 28), 'x >= 2024-02-28')\nbuilder.add_constraint(x <= Date(2024, 3, 1), 'x <= 2024-03-01')",
                "variables": ["x"],
                "coverage_tags": ["leap_boundary"],
                "expected_satisfiable": True,
            },
            {
                "id": "constraint_{}",
                "description": "Month vs days contrast",
                "constraint_code": "x = builder.add_date_var('x')\nbuilder.add_constraint(x >= Date(2023, 1, 1), 'x >= 2023-01-01')\nbuilder.add_constraint((x + Period(0, 1, 0)) > (x + Period(0, 0, 31)), 'month > 31 days')",
                "variables": ["x"],
                "coverage_tags": ["month_vs_days"],
                "expected_satisfiable": False,
            },
            {
                "id": "constraint_{}",
                "description": "Year vs days contrast",
                "constraint_code": "builder.add_constraint(x >= Date(2024, 1, 1), 'x >= 2024-01-01')\nbuilder.add_constraint((x + Period(1, 0, 0)) == (x + Period(0, 0, 366)), '1 year = 366 days')",
                "variables": ["x"],
                "coverage_tags": ["year_vs_days"],
                "expected_satisfiable": False,
            },
            {
                "id": "constraint_{}",
                "description": "End of month rollover",
                "constraint_code": "builder.add_constraint(x >= Date(2023, 1, 31), 'x >= 2023-01-31')\nbuilder.add_constraint((x + Period(0, 1, 0)) <= Date(2023, 3, 1), 'x + 1 month <= 2023-03-01')",
                "variables": ["x"],
                "coverage_tags": ["eom"],
                "expected_satisfiable": True,
            },
            {
                "id": "constraint_{}",
                "description": "Chain of additions",
                "constraint_code": "builder.add_constraint(x >= Date(2023, 6, 1), 'x >= 2023-06-01')\nbuilder.add_constraint((x + Period(0, 1, 0) + Period(0, 0, 15)) == y, 'x + 1 month + 15 days = y')\nbuilder.add_constraint(y >= Date(2023, 6, 1), 'y >= 2023-06-01')",
                "variables": ["x", "y"],
                "coverage_tags": ["chain_add", "multi_var"],
                "expected_satisfiable": True,
            },
            {
                "id": "constraint_{}",
                "description": "Multi-variable relations",
                "constraint_code": "builder.add_constraint(x >= Date(2024, 1, 1), 'x >= 2024-01-01')\nbuilder.add_constraint(y >= Date(2024, 1, 1), 'y >= 2024-01-01')\nbuilder.add_constraint(z >= Date(2024, 1, 1), 'z >= 2024-01-01')\nbuilder.add_constraint(x < y, 'x < y')\nbuilder.add_constraint(y < z, 'y < z')\nbuilder.add_constraint((x + Period(0, 1, 0)) < y, 'x + 1 month < y')",
                "variables": ["x", "y", "z"],
                "coverage_tags": ["multi_var", "ineq_window"],
                "expected_satisfiable": True,
            },
            {
                "id": "constraint_{}",
                "description": "Tight range UNSAT case",
                "constraint_code": "builder.add_constraint(x >= Date(2023, 2, 28), 'x >= 2023-02-28')\nbuilder.add_constraint(x <= Date(2023, 2, 28), 'x <= 2023-02-28')\nbuilder.add_constraint((x + Period(0, 0, 1)) > Date(2023, 3, 1), 'x + 1 day > 2023-03-01')",
                "variables": ["x"],
                "coverage_tags": ["ineq_window", "eom"],
                "expected_satisfiable": False,
            },
        ]

    def generate_constraints(self, num_constraints: int = 8) -> list:
        """Generate mock constraints with coverage tags."""
        constraints = []

        # Ensure we get a good mix of coverage tags
        selected_templates = []

        # Always include at least one of each coverage tag
        coverage_tags = [
            "leap_boundary",
            "eom",
            "year_vs_days",
            "month_vs_days",
            "chain_add",
            "ineq_window",
            "multi_var",
        ]
        for tag in coverage_tags:
            tag_templates = [
                t for t in self.constraint_templates if tag in t["coverage_tags"]
            ]
            if tag_templates:
                selected_templates.append(random.choice(tag_templates))

        # Fill remaining slots with random templates
        while len(selected_templates) < num_constraints:
            selected_templates.append(random.choice(self.constraint_templates))

        # Shuffle and take the requested number
        random.shuffle(selected_templates)
        selected_templates = selected_templates[:num_constraints]

        for template in selected_templates:
            constraint = template.copy()
            # Remove the old id template and add sequential ID
            del constraint["id"]
            constraint["id"] = str(get_next_id())
            constraints.append(constraint)

        return constraints

    def save_constraints(self, constraints: list, filename: str):
        """Save constraints to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(constraints, f, indent=2)
        print(f"Saved {len(constraints)} mock constraints to {filename}")


def main():
    """Generate mock constraints."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate mock date constraints with coverage tags"
    )
    parser.add_argument(
        "--num", type=int, default=8, help="Number of constraints to generate"
    )
    parser.add_argument(
        "--output", default="mock_constraints.json", help="Output filename"
    )

    args = parser.parse_args()

    client = MockLLMClient()
    constraints = client.generate_constraints(args.num)
    client.save_constraints(constraints, args.output)
    print(f"Successfully generated {len(constraints)} mock constraints")


if __name__ == "__main__":
    main()
