import unittest

from src.agents.sql_safety_agent import SQLSafetyAgent


class SQLSafetyAgentTest(unittest.TestCase):
    def test_blocks_delete_without_where(self):
        result = SQLSafetyAgent().check("DELETE FROM orders")

        self.assertFalse(result.safe)
        self.assertEqual("dangerous", result.risk_level)
        self.assertTrue(result.requires_confirmation)

    def test_warns_on_select_star_without_limit(self):
        result = SQLSafetyAgent().check("SELECT * FROM users")

        self.assertTrue(result.safe)
        self.assertEqual("medium", result.risk_level)
        self.assertIn("Query has no LIMIT and may return many rows.", result.warnings)

    def test_safe_limited_select(self):
        result = SQLSafetyAgent().check("SELECT id, name FROM users LIMIT 50")

        self.assertTrue(result.safe)
        self.assertEqual("safe", result.risk_level)

    def test_blocks_multi_statement_sql(self):
        result = SQLSafetyAgent().check("SELECT id FROM users; SELECT id FROM orders;")

        self.assertFalse(result.safe)
        self.assertEqual("dangerous", result.risk_level)

    def test_blocks_insert_in_read_only_mode(self):
        result = SQLSafetyAgent().check("INSERT INTO users (name) VALUES ('Ada')")

        self.assertFalse(result.safe)
        self.assertEqual("dangerous", result.risk_level)


if __name__ == "__main__":
    unittest.main()
