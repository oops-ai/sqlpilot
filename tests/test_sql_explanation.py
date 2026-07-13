import unittest

from src.agents.sql_explanation_agent import SQLExplanationAgent


class SQLExplanationAgentTest(unittest.TestCase):
    def test_explains_tables_filters_and_performance_notes(self):
        sql = "SELECT * FROM orders WHERE status = 'paid' ORDER BY created_at"

        explanation = SQLExplanationAgent().explain(sql)

        self.assertEqual(["orders"], explanation.tables_used)
        self.assertEqual(["status = 'paid'"], explanation.filters)
        self.assertIn("SELECT * can read more data than needed.", explanation.performance_notes)


if __name__ == "__main__":
    unittest.main()
