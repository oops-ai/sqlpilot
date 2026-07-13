import os
from dataclasses import dataclass
from typing import List, Optional
from uuid import uuid4

from src.database.connection import DatabaseConfig, PostgresConnectionFactory
from src.services.app_storage import AppStorage


@dataclass
class ConnectionProfile:
    id: str
    name: str
    host: str
    port: int
    database_name: str
    username: str
    password_env_var: Optional[str] = None

    def dsn(self) -> str:
        password = os.getenv(self.password_env_var or "", "")
        auth = self.username if not password else f"{self.username}:{password}"
        return f"postgresql://{auth}@{self.host}:{self.port}/{self.database_name}"


class ConnectionService:
    def __init__(self, storage: AppStorage):
        self.storage = storage

    def create(
        self,
        name: str,
        host: str,
        database_name: str,
        username: str,
        port: int = 5432,
        password_env_var: Optional[str] = None,
    ) -> ConnectionProfile:
        profile = ConnectionProfile(str(uuid4()), name, host, port, database_name, username, password_env_var)
        self.storage.execute(
            """
            INSERT INTO connection_profiles
                (id, name, host, port, database_name, username, password_env_var)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id,
                profile.name,
                profile.host,
                profile.port,
                profile.database_name,
                profile.username,
                profile.password_env_var,
            ),
        )
        return profile

    def list(self) -> List[ConnectionProfile]:
        rows = self.storage.fetchall(
            """
            SELECT id, name, host, port, database_name, username, password_env_var
            FROM connection_profiles
            ORDER BY created_at DESC
            """
        )
        return [ConnectionProfile(**row) for row in rows]

    def get(self, connection_id: str) -> Optional[ConnectionProfile]:
        row = self.storage.fetchone(
            """
            SELECT id, name, host, port, database_name, username, password_env_var
            FROM connection_profiles
            WHERE id = ?
            """,
            (connection_id,),
        )
        return ConnectionProfile(**row) if row else None

    def connect(self, connection_id: str):
        profile = self.get(connection_id)
        if not profile:
            raise ValueError(f"Unknown connection profile: {connection_id}")
        return PostgresConnectionFactory(DatabaseConfig(profile.dsn())).connect()

    def test(self, connection_id: str) -> bool:
        with self.connect(connection_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1
