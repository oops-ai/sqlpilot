import unittest
from decimal import Decimal

from src.agents.result_agent import QueryResultAgent


class QueryResultAgentTest(unittest.TestCase):
    def test_suggests_line_chart_for_iso_date_strings_and_decimal_values(self):
        result = QueryResultAgent().summarize(
            columns=["month", "total_sales"],
            rows=[
                {"month": "2024-01-01T00:00:00-05:00", "total_sales": Decimal("195.50")},
                {"month": "2024-02-01T00:00:00-05:00", "total_sales": Decimal("270.24")},
            ],
        )

        self.assertEqual("Line chart", result.visualization_suggestion)

    def test_suggests_line_chart_for_iso_date_strings_and_numeric_strings(self):
        result = QueryResultAgent().summarize(
            columns=["bucket", "total_sales"],
            rows=[
                {"bucket": "2024-01-01T00:00:00-05:00", "total_sales": "195.50"},
                {"bucket": "2024-02-01T00:00:00-05:00", "total_sales": "270.24"},
            ],
        )

        self.assertEqual("Line chart", result.visualization_suggestion)

    def test_suggests_bar_chart_for_category_and_numeric_string(self):
        result = QueryResultAgent().summarize(
            columns=["status", "order_count"],
            rows=[
                {"status": "paid", "order_count": "4"},
                {"status": "refunded", "order_count": "1"},
            ],
        )

        self.assertEqual("Bar chart", result.visualization_suggestion)


if __name__ == "__main__":
    unittest.main()
