import unittest

from src.agents.sql_generation_agent import SQLGenerationAgent
from src.database.schema_loader import ColumnInfo, DatabaseSchema, TableInfo


class SQLGenerationAgentTest(unittest.TestCase):
    def orders_schema(self):
        return DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="orders",
                    columns=[
                        ColumnInfo("id", "uuid"),
                        ColumnInfo("order_date", "timestamp"),
                        ColumnInfo("total_amount", "numeric"),
                        ColumnInfo("status", "text"),
                    ],
                )
            ]
        )

    def test_generates_monthly_total_with_schema_columns(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="orders",
                    columns=[
                        ColumnInfo("id", "uuid"),
                        ColumnInfo("order_date", "timestamp"),
                        ColumnInfo("total_amount", "numeric"),
                    ],
                )
            ]
        )

        result = SQLGenerationAgent().generate("Show total sales by month for 2024", schema)

        self.assertIn("FROM orders", result.sql)
        self.assertIn("DATE_TRUNC('month', order_date)", result.sql)
        self.assertIn("SUM(total_amount)", result.sql)
        self.assertIn("LIMIT 100", result.sql)

    def test_honors_explicit_row_limit_in_request(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="orders",
                    columns=[
                        ColumnInfo("id", "uuid"),
                        ColumnInfo("order_date", "timestamp"),
                        ColumnInfo("total_amount", "numeric"),
                    ],
                )
            ]
        )

        result = SQLGenerationAgent().generate("Show top 5 rows from orders", schema)

        self.assertIn("LIMIT 5", result.sql)

    def test_prefers_requested_table_for_generic_row_request(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="audit_events",
                    columns=[ColumnInfo("id", "uuid")],
                ),
                TableInfo(
                    name="imported_customers",
                    columns=[ColumnInfo("customer_id", "text"), ColumnInfo("customer_city", "text")],
                ),
            ]
        )

        result = SQLGenerationAgent().generate(
            "show top 5 rows",
            schema,
            preferred_table_name="imported_customers",
        )

        self.assertIn("FROM imported_customers", result.sql)
        self.assertIn("LIMIT 5", result.sql)

    def test_generic_row_request_bypasses_llm_when_preferred_table_exists(self):
        class WrongTableLLM:
            def complete(self, prompt):
                return '{"sql":"SELECT * FROM audit_events LIMIT 5","explanation":"ok","safety_notes":[]}'

        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="audit_events",
                    columns=[ColumnInfo("id", "uuid")],
                ),
                TableInfo(
                    name="imported_olist_customers_dataset",
                    columns=[ColumnInfo("customer_id", "text"), ColumnInfo("customer_city", "text")],
                ),
            ]
        )

        result = SQLGenerationAgent(llm_service=WrongTableLLM()).generate(
            "show top 5 rows",
            schema,
            preferred_table_name="imported_olist_customers_dataset",
        )

        self.assertIn("FROM imported_olist_customers_dataset", result.sql)
        self.assertNotIn("audit_events", result.sql)

    def test_explicit_row_limit_overrides_llm_limit(self):
        class WrongLimitLLM:
            def complete(self, prompt):
                return '{"sql":"SELECT * FROM orders LIMIT 3","explanation":"ok","safety_notes":[]}'

        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="orders",
                    columns=[
                        ColumnInfo("id", "uuid"),
                        ColumnInfo("order_date", "timestamp"),
                        ColumnInfo("total_amount", "numeric"),
                    ],
                )
            ]
        )

        result = SQLGenerationAgent(llm_service=WrongLimitLLM()).generate("Show top 5 rows from orders", schema)

        self.assertIn("LIMIT 5", result.sql)
        self.assertNotIn("LIMIT 3", result.sql)

    def test_requires_schema_instead_of_hallucinating(self):
        result = SQLGenerationAgent().generate("Show customers")

        self.assertTrue(result.sql.startswith("-- Schema is required"))
        self.assertIn("schema", result.explanation.lower())

    def test_falls_back_when_local_llm_is_unavailable(self):
        class BrokenLLM:
            def complete(self, prompt):
                raise ConnectionError("ollama unavailable")

        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="orders",
                    columns=[
                        ColumnInfo("id", "uuid"),
                        ColumnInfo("order_date", "timestamp"),
                        ColumnInfo("total_amount", "numeric"),
                    ],
                )
            ]
        )

        result = SQLGenerationAgent(llm_service=BrokenLLM()).generate("Show total sales by month", schema)

        self.assertIn("FROM orders", result.sql)
        self.assertIn("SUM(total_amount)", result.sql)

    def test_identifier_validation_handles_extract_from_column(self):
        schema = self.orders_schema()
        sql = (
            "SELECT EXTRACT(YEAR FROM order_date) AS year, "
            "SUM(total_amount) AS total_sales FROM orders GROUP BY year"
        )

        self.assertTrue(SQLGenerationAgent()._uses_known_identifiers(sql, schema))

    def test_identifier_validation_allows_table_aliases_and_output_aliases(self):
        sql = (
            "SELECT DATE_TRUNC('month', o.order_date) AS month, "
            "SUM(o.total_amount) AS total_sales "
            "FROM orders AS o "
            "WHERE o.status = 'paid' "
            "GROUP BY DATE_TRUNC('month', o.order_date) "
            "ORDER BY month"
        )

        self.assertTrue(SQLGenerationAgent()._uses_known_identifiers(sql, self.orders_schema()))

    def test_identifier_validation_rejects_unknown_unqualified_column(self):
        sql = "SELECT made_up_column FROM orders LIMIT 10"

        self.assertFalse(SQLGenerationAgent()._uses_known_identifiers(sql, self.orders_schema()))

    def test_identifier_validation_rejects_unknown_qualified_column(self):
        sql = "SELECT o.made_up_column FROM orders AS o LIMIT 10"

        self.assertFalse(SQLGenerationAgent()._uses_known_identifiers(sql, self.orders_schema()))

    def test_llm_result_is_rejected_when_column_is_unknown(self):
        class BadColumnLLM:
            def complete(self, prompt):
                return (
                    '{"sql":"SELECT total_revenue FROM orders LIMIT 10",'
                    '"explanation":"bad","safety_notes":[]}'
                )

        result = SQLGenerationAgent(llm_service=BadColumnLLM()).generate("show revenue", self.orders_schema())

        self.assertTrue(result.sql.startswith("-- Generated SQL referenced unknown schema identifiers."))


if __name__ == "__main__":
    unittest.main()
