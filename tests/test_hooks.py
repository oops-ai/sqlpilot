import unittest

from src.hooks.after_execution import AfterExecutionHook
from src.hooks.before_execution import BeforeExecutionHook
from src.services.preference_service import PreferenceService
from src.services.query_history_service import QueryHistoryService


class HookTest(unittest.TestCase):
    def test_before_execution_blocks_dangerous_query(self):
        result = BeforeExecutionHook().run("DROP TABLE users")

        self.assertEqual("dangerous", result.risk_level)
        self.assertTrue(result.requires_confirmation)
        self.assertEqual("high", result.estimated_cost)

    def test_after_execution_summarizes_and_saves_history(self):
        history = QueryHistoryService()
        preferences = PreferenceService()
        hook = AfterExecutionHook(history_service=history, preference_service=preferences)

        result = hook.run(
            sql="SELECT month, total_sales FROM monthly_sales",
            columns=["month", "total_sales"],
            rows=[{"month": "2024-01-01", "total_sales": 100}],
            execution_time_ms=12,
            safety_level="safe",
            user_request="Show sales by month",
            tables_used=["orders"],
        )

        self.assertEqual(1, result["row_count"])
        self.assertEqual("Line chart", result["visualization_suggestion"])
        self.assertEqual(1, len(history.list_recent()))
        self.assertEqual("Line chart", preferences.get("last_visualization_suggestion"))

    def test_after_execution_learns_limit_and_recent_tables(self):
        preferences = PreferenceService()
        hook = AfterExecutionHook(history_service=QueryHistoryService(), preference_service=preferences)

        result = hook.run(
            sql="SELECT id FROM query_history LIMIT 25",
            columns=["id"],
            rows=[{"id": "1"}],
            execution_time_ms=5,
            safety_level="safe",
            tables_used=["query_history"],
        )

        self.assertIn("last_limit=25", result["learned_preferences"])
        self.assertEqual("25", preferences.get("last_limit"))
        self.assertEqual('["query_history"]', preferences.get("recent_tables"))


if __name__ == "__main__":
    unittest.main()
