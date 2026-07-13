import unittest
from decimal import Decimal

from src.database.schema_loader import ColumnInfo, DatabaseSchema, TableInfo
from src.services.dataset_import_service import DatasetImportService


class FakeCursor:
    def __init__(self):
        self.commands = []
        self.executed_many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.commands.append((sql, params))

    def executemany(self, sql, params_seq):
        self.executed_many.append((sql, list(params_seq)))


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


class FakeConnectionService:
    def __init__(self):
        self.connection = FakeConnection()

    def connect(self, connection_id):
        return self.connection


class FakeSchemaService:
    def __init__(self):
        self.refresh_calls = []

    def refresh(self, connection_id):
        self.refresh_calls.append(connection_id)
        return DatabaseSchema.from_tables(
            [
                TableInfo(
                    name="imported_sales",
                    columns=[ColumnInfo("order_id", "TEXT"), ColumnInfo("amount", "NUMERIC")],
                )
            ]
        )


class DatasetImportServiceTest(unittest.TestCase):
    def test_imports_csv_text_and_infers_types(self):
        connection_service = FakeConnectionService()
        schema_service = FakeSchemaService()
        service = DatasetImportService(connection_service, schema_service)

        result = service.import_dataset(
            "conn-1",
            csv_text="order_id,amount,shipped\n1,10.50,true\n2,20.00,false\n",
            table_name="sales",
        )

        self.assertEqual("sales", result.table_name)
        self.assertEqual(2, result.row_count)
        self.assertEqual(["order_id", "amount", "shipped"], result.columns)
        self.assertEqual(1, len(schema_service.refresh_calls))
        self.assertIn(
            'CREATE TABLE IF NOT EXISTS "sales" ("order_id" TEXT, "amount" NUMERIC, "shipped" BOOLEAN)',
            connection_service.connection.cursor_instance.commands[0][0],
        )
        self.assertEqual(1, len(connection_service.connection.cursor_instance.executed_many))
        inserted_rows = connection_service.connection.cursor_instance.executed_many[0][1]
        self.assertEqual(("1", Decimal("10.50"), True), inserted_rows[0])

    def test_imports_from_url(self):
        connection_service = FakeConnectionService()
        schema_service = FakeSchemaService()
        service = DatasetImportService(connection_service, schema_service)
        service._fetch_url = lambda source_url: "name,value\nAda,5\n"

        result = service.import_dataset("conn-1", source_url="https://example.com/data.csv")

        self.assertEqual("url", result.source_type)
        self.assertEqual("imported_data", result.table_name)
        self.assertEqual(1, result.row_count)

    def test_cleanup_imported_datasets_drops_registered_tables(self):
        import tempfile
        from pathlib import Path

        from src.services.app_storage import AppStorage

        class CleanupCursor(FakeCursor):
            def execute(self, sql, params=None):
                super().execute(sql, params)

        class CleanupConnection:
            def __init__(self):
                self.cursor_instance = CleanupCursor()
                self.committed = False
                self.rolled_back = False
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        class CleanupConnectionService:
            def __init__(self, storage):
                self.storage = storage
                self.connection = CleanupConnection()

            def connect(self, connection_id):
                return self.connection

        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(f"sqlite:///{Path(tmp) / 'app.db'}")
            storage.register_imported_dataset("conn-1", "imported_sales", "csv")
            connection_service = CleanupConnectionService(storage)
            schema_service = FakeSchemaService()
            service = DatasetImportService(connection_service, schema_service)

            dropped = service.cleanup_imported_datasets()

            self.assertEqual(["imported_sales"], dropped)
            self.assertEqual([], storage.list_imported_datasets())
            self.assertIn('DROP TABLE IF EXISTS "imported_sales"', connection_service.connection.cursor_instance.commands[0][0])


if __name__ == "__main__":
    unittest.main()
