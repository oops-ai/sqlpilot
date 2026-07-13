import tempfile
import unittest
from pathlib import Path

from src.api.routes import ApiHandlers
from src.api.schemas import AskDatabaseRequest, CheckSafetyRequest, ConnectionCreateRequest, GenerateSqlRequest, InferJoinRequest
from src.agents.sql_generation_agent import SqlGenerationResult
from src.database.schema_loader import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from src.services.app_storage import AppStorage


class ApiHandlersTest(unittest.TestCase):
    def test_ask_database_generates_and_executes_answer(self):
        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.description = [("month",), ("total_sales",)]
                self.plan_payload = [{"Plan": {"Total Cost": 10, "Plan Rows": 1}}]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def execute(self, sql, params=None):
                self.commands.append(sql)

            def fetchall(self):
                return [("2024-01-01", 100)]

            def fetchone(self):
                return (self.plan_payload,)

        class FakeConnection:
            def __init__(self):
                self.cursor_instance = FakeCursor()

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
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
            handlers = ApiHandlers(schema=schema, storage=storage)
            handlers.connection_service.connect = lambda connection_id: FakeConnection()

            result = handlers.ask_database(
                AskDatabaseRequest(
                    connection_id="conn-1",
                    natural_language_request="total sales by month",
                )
            )

            self.assertIn("FROM orders", result["sql"])
            self.assertEqual(1, result["row_count"])
            self.assertEqual(1, len(handlers.query_history()))

    def test_ask_database_falls_back_to_recent_imported_table(self):
        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.description = [("id",), ("name",)]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def execute(self, sql, params=None):
                self.commands.append(sql)
                if sql.startswith("EXPLAIN (FORMAT JSON)") and "audit_events" in sql:
                    raise RuntimeError("bad generated sql")

            def fetchall(self):
                return [(1, "Ada")]

            def fetchone(self):
                return ([{"Plan": {"Total Cost": 10, "Plan Rows": 1}}],)

        class FakeConnection:
            def __init__(self):
                self.cursor_instance = FakeCursor()

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            schema = DatabaseSchema.from_tables(
                [
                    TableInfo(name="audit_events", columns=[ColumnInfo("id", "uuid")]),
                    TableInfo(name="imported_sales", columns=[ColumnInfo("id"), ColumnInfo("name")]),
                ]
            )
            handlers = ApiHandlers(schema=schema, storage=storage)
            handlers.connection_service.connect = lambda connection_id: FakeConnection()
            handlers.preference_service.set("recent_imported_table", "imported_sales")
            handlers.generation_agent.generate = lambda *args, **kwargs: SqlGenerationResult(
                sql="SELECT * FROM audit_events WHERE id BETWEEN 10 AND 20",
                explanation="bad",
                safety_notes=[],
            )

            result = handlers.ask_database(
                AskDatabaseRequest(
                    connection_id="conn-1",
                    natural_language_request="show top 5 rows",
                )
            )

            self.assertIn("imported_sales", result["sql"])
            self.assertEqual(1, result["row_count"])

    def test_ask_database_prefers_recent_imported_table_for_generic_row_requests(self):
        class FakeCursor:
            def __init__(self):
                self.commands = []
                self.description = [("customer_id",), ("customer_city",)]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def execute(self, sql, params=None):
                self.commands.append(sql)

            def fetchall(self):
                return [(1, "franca"), (2, "sao paulo"), (3, "campinas"), (4, "santos"), (5, "recife")]

            def fetchone(self):
                return ([{"Plan": {"Total Cost": 10, "Plan Rows": 5}}],)

        class FakeConnection:
            def __init__(self):
                self.cursor_instance = FakeCursor()

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            schema = DatabaseSchema.from_tables(
                [
                    TableInfo(name="audit_events", columns=[ColumnInfo("id", "uuid")]),
                    TableInfo(name="imported_customers", columns=[ColumnInfo("customer_id"), ColumnInfo("customer_city")]),
                ]
            )
            handlers = ApiHandlers(schema=schema, storage=storage)
            handlers.connection_service.connect = lambda connection_id: FakeConnection()
            handlers.preference_service.set("recent_imported_table", "imported_customers")

            result = handlers.ask_database(
                AskDatabaseRequest(
                    connection_id="conn-1",
                    natural_language_request="show top 5 rows",
                )
            )

            self.assertIn("imported_customers", result["sql"])
            self.assertEqual(5, result["row_count"])

    def test_generate_sql_saves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
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
            handlers = ApiHandlers(schema=schema, storage=storage)

            result = handlers.generate_sql(GenerateSqlRequest(natural_language_request="total sales by month"))

            self.assertIn("FROM orders", result["sql"])
            self.assertEqual(1, len(handlers.query_history()))

    def test_connection_profile_can_be_created_and_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            handlers = ApiHandlers(storage=storage)

            created = handlers.create_connection(
                ConnectionCreateRequest(
                    name="Local",
                    host="localhost",
                    database_name="app",
                    username="postgres",
                )
            )

            self.assertEqual("Local", created["name"])
            self.assertEqual(1, len(handlers.list_connections()))

    def test_check_safety_blocks_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            handlers = ApiHandlers(storage=AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}"))

            result = handlers.check_safety(CheckSafetyRequest(sql="UPDATE users SET name = 'Ada'"))

            self.assertFalse(result["safe"])
            self.assertEqual("dangerous", result["risk_level"])

    def test_infer_join_returns_candidates_from_loaded_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            handlers = ApiHandlers(storage=storage)
            connection = handlers.create_connection(
                ConnectionCreateRequest(
                    name="Local",
                    host="localhost",
                    database_name="app",
                    username="postgres",
                )
            )
            schema = DatabaseSchema.from_tables(
                [
                    TableInfo(name="customers", columns=[ColumnInfo("id")], primary_key="id"),
                    TableInfo(
                        name="orders",
                        columns=[ColumnInfo("id"), ColumnInfo("customer_id")],
                        foreign_keys=[ForeignKeyInfo("customer_id", "customers", "id")],
                    ),
                ]
            )
            storage.execute(
                """
                INSERT INTO schema_snapshots (connection_id, schema_json)
                VALUES (?, ?)
                """,
                (connection["id"], __import__("json").dumps(schema.to_dict())),
            )

            result = handlers.infer_join(
                InferJoinRequest(
                    connection_id=connection["id"],
                    left_table="customers",
                    right_table="orders",
                )
            )

            self.assertEqual("orders.customer_id = customers.id", result[0]["condition"])


if __name__ == "__main__":
    unittest.main()
