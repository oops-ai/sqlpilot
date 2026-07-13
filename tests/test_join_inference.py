import unittest

from src.database.schema_loader import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from src.services.join_inference_service import JoinInferenceService


class JoinInferenceServiceTest(unittest.TestCase):
    def test_prefers_explicit_foreign_key(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(name="customers", columns=[ColumnInfo("id")], primary_key="id"),
                TableInfo(
                    name="orders",
                    columns=[ColumnInfo("id"), ColumnInfo("customer_id")],
                    primary_key="id",
                    foreign_keys=[ForeignKeyInfo("customer_id", "customers", "id")],
                ),
            ]
        )

        candidates = JoinInferenceService().infer(schema, "customers", "orders")

        self.assertEqual(1, len(candidates))
        self.assertEqual("orders.customer_id = customers.id", candidates[0].condition)
        self.assertEqual("high", candidates[0].confidence)

    def test_uses_common_naming_pattern(self):
        schema = DatabaseSchema.from_tables(
            [
                TableInfo(name="accounts", columns=[ColumnInfo("id")], primary_key="id"),
                TableInfo(name="events", columns=[ColumnInfo("id"), ColumnInfo("account_id")]),
            ]
        )

        candidates = JoinInferenceService().infer(schema, "accounts", "events")

        self.assertEqual("events.account_id = accounts.id", candidates[0].condition)
        self.assertEqual("medium", candidates[0].confidence)


if __name__ == "__main__":
    unittest.main()
