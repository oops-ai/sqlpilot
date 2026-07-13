import tempfile
import unittest
from pathlib import Path

from src.config import Settings
from src.database.query_executor import QueryExecutor
from src.database.schema_loader import ColumnInfo, DatabaseSchema, IndexInfo, TableInfo
from src.services.app_storage import AppStorage
from src.services.query_history_service import QueryHistoryService


class FakeCursor:
    def __init__(self):
        self.commands = []
        self.description = [("id",), ("name",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql):
        self.commands.append(sql)

    def fetchall(self):
        return [(1, "Ada")]


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


class PersistenceAndExecutionTest(unittest.TestCase):
    def test_query_history_persists_to_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            history = QueryHistoryService(storage)

            history.save(
                generated_sql="SELECT id FROM users LIMIT 1",
                safety_level="safe",
                user_request="show users",
                executed=True,
                row_count=1,
                tables_used=["users"],
            )

            entries = history.list_recent()
            self.assertEqual(1, len(entries))
            self.assertEqual(["users"], entries[0].tables_used)

    def test_schema_round_trip_includes_indexes(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="users",
                    columns=[ColumnInfo("id", "uuid", nullable=False)],
                    primary_key="id",
                    indexes=[IndexInfo("users_pkey", ["id"], unique=True)],
                )
            ]
        )

        restored = DatabaseSchema.from_dict(schema.to_dict())

        self.assertEqual("users", restored.get_table("users").name)
        self.assertEqual("users_pkey", restored.get_table("users").indexes[0].name)

    def test_query_executor_uses_read_only_transaction(self):
        connection = FakeConnection()
        executor = QueryExecutor(settings=Settings(statement_timeout_ms=1234))

        result = executor.execute("SELECT id, name FROM users LIMIT 1", connection)

        self.assertEqual(1, result.row_count)
        self.assertTrue(connection.committed)
        self.assertIn("SET TRANSACTION READ ONLY", connection.cursor_instance.commands)
        self.assertIn("SET LOCAL statement_timeout = 1234", connection.cursor_instance.commands)


if __name__ == "__main__":
    unittest.main()
