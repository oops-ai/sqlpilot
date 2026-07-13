import json
import tempfile
import unittest
from pathlib import Path

from src.api.routes import ApiHandlers
from src.database.schema_loader import ColumnInfo, DatabaseSchema, TableInfo
from src.mcp.server import SqlMcpServer
from src.services.app_storage import AppStorage


class FakeCursor:
    def __init__(self, rows=None, description=None):
        self.rows = rows or []
        self.description = description
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.commands.append(sql)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, rows=None, description=None):
        self.cursor_instance = FakeCursor(rows=rows, description=description)
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class McpServerTest(unittest.TestCase):
    def test_tools_list_includes_execute_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            handlers = ApiHandlers(storage=storage, use_llm=False)
            server = SqlMcpServer(handlers=handlers)

            response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

            tool_names = [tool["name"] for tool in response["result"]["tools"]]
            self.assertIn("execute_sql", tool_names)
            self.assertIn("generate_sql", tool_names)

    def test_app_sql_write_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            handlers = ApiHandlers(storage=storage, use_llm=False)
            server = SqlMcpServer(handlers=handlers)

            blocked = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "execute_sql",
                        "arguments": {
                            "database": "app",
                            "sql": "CREATE TABLE demo_items (id INTEGER PRIMARY KEY, name TEXT)",
                        },
                    },
                }
            )

            self.assertTrue(blocked["result"]["content"][0]["text"].startswith("{\n  \"blocked\": true"))

            allowed = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "execute_sql",
                        "arguments": {
                            "database": "app",
                            "sql": "CREATE TABLE demo_items (id INTEGER PRIMARY KEY, name TEXT)",
                            "confirmed": True,
                        },
                    },
                }
            )

            self.assertIn('"row_count": 0', allowed["result"]["content"][0]["text"])

    def test_target_read_uses_connected_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            handlers = ApiHandlers(storage=storage, use_llm=False)
            server = SqlMcpServer(handlers=handlers)

            handlers.connection_service.connect = lambda connection_id: FakeConnection(
                rows=[(1, "Ada")],
                description=[("id",), ("name",)],
            )

            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "execute_sql",
                        "arguments": {
                            "database": "target",
                            "connection_id": "conn-1",
                            "sql": "SELECT id, name FROM users LIMIT 1",
                        },
                    },
                }
            )

            payload = json.loads(response["result"]["content"][0]["text"])
            self.assertEqual(1, payload["row_count"])
            self.assertEqual("Ada", payload["rows"][0]["name"])


if __name__ == "__main__":
    unittest.main()
