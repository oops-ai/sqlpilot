import json
from typing import Optional

from src.database.schema_loader import DatabaseSchema, PostgresSchemaLoader
from src.services.app_storage import AppStorage
from src.services.connection_service import ConnectionService


class SchemaService:
    def __init__(self, storage: AppStorage, connection_service: ConnectionService):
        self.storage = storage
        self.connection_service = connection_service
        self.loader = PostgresSchemaLoader()

    def refresh(self, connection_id: str) -> DatabaseSchema:
        with self.connection_service.connect(connection_id) as connection:
            schema = self.loader.load(connection)
        self.storage.execute(
            """
            INSERT INTO schema_snapshots (connection_id, schema_json, refreshed_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(connection_id) DO UPDATE SET
                schema_json = excluded.schema_json,
                refreshed_at = CURRENT_TIMESTAMP
            """,
            (connection_id, json.dumps(schema.to_dict())),
        )
        return schema

    def get(self, connection_id: str) -> Optional[DatabaseSchema]:
        row = self.storage.fetchone(
            "SELECT schema_json FROM schema_snapshots WHERE connection_id = ?",
            (connection_id,),
        )
        if not row:
            return None
        schema_json = row["schema_json"]
        if isinstance(schema_json, str):
            schema_json = json.loads(schema_json)
        return DatabaseSchema.from_dict(schema_json)
