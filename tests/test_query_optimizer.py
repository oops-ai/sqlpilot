import unittest

from src.agents.sql_optimization_agent import SQLOptimizationAgent


class SQLOptimizationAgentTest(unittest.TestCase):
    def test_adds_limit_for_exploratory_select(self):
        result = SQLOptimizationAgent().optimize("SELECT id, name FROM users")

        self.assertIn("Exploratory SELECT has no LIMIT.", result.issues_found)
        self.assertTrue(result.optimized_query.endswith("LIMIT 100;"))

    def test_suggests_index_for_filter(self):
        result = SQLOptimizationAgent().optimize("SELECT id FROM orders WHERE customer_id = 1 LIMIT 10")

        self.assertIn("Consider an index on `customer_id`", result.index_suggestions[0])

    def test_uses_explain_plan_for_sequential_scan_recommendation(self):
        plan = {
            "Node Type": "Seq Scan",
            "Relation Name": "orders",
            "Plan Rows": 50000,
            "Filter": "(customer_id = 123)",
        }

        result = SQLOptimizationAgent().optimize("SELECT id FROM orders WHERE customer_id = 123", plan=plan)

        self.assertIn("Query plan uses a sequential scan on `orders`.", result.issues_found)
        self.assertIn("Consider an index on `orders.customer_id` for this filter.", result.index_suggestions)


if __name__ == "__main__":
    unittest.main()
