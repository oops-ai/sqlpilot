import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _normalize_row_value(column_name: str, value: Any) -> Any:
    if isinstance(value, str) and (
        column_name.endswith("_json")
        or column_name in {"schema_json", "metadata_json", "tables_used_json", "tags_json"}
    ):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


class AppStorage:
    def __init__(self, database_url: str = "sqlite:///./ai_sql_copilot.db"):
        self.database_url = database_url
        self.dialect = self._detect_dialect(database_url)
        if self.dialect == "sqlite":
            self.path = Path(database_url.replace("sqlite:///", "", 1))
            if self.path.parent != Path("."):
                self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _detect_dialect(self, database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return "sqlite"
        if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
            return "postgres"
        raise ValueError("Only sqlite:/// and postgresql:// app storage URLs are supported.")

    def connect(self):
        if self.dialect == "sqlite":
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            return connection

        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - environment issue
            raise RuntimeError("Install psycopg to connect to PostgreSQL app storage.") from exc

        return psycopg.connect(self.database_url, row_factory=dict_row)

    @contextmanager
    def _cursor(self, connection):
        cursor = connection.cursor()
        try:
            yield cursor
        finally:
            close = getattr(cursor, "close", None)
            if close:
                close()

    def initialize(self) -> None:
        with self.connect() as connection:
            statements = self._schema_statements()
            if self.dialect == "sqlite":
                connection.executescript(statements)
            else:
                with self._cursor(connection) as cursor:
                    for statement in statements.split(";"):
                        sql = statement.strip()
                        if sql:
                            cursor.execute(sql)
                self._seed_postgres(connection)

    def _schema_statements(self) -> str:
        return """
                CREATE TABLE IF NOT EXISTS connection_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    database_name TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password_env_var TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS schema_snapshots (
                    connection_id TEXT PRIMARY KEY,
                    schema_json TEXT NOT NULL,
                    refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS query_history (
                    id TEXT PRIMARY KEY,
                    user_request TEXT,
                    generated_sql TEXT NOT NULL,
                    executed INTEGER NOT NULL DEFAULT 0,
                    execution_time_ms INTEGER,
                    row_count INTEGER,
                    database_name TEXT,
                    tables_used_json TEXT NOT NULL DEFAULT '[]',
                    safety_level TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    preference_key TEXT PRIMARY KEY,
                    preference_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS imported_dataset_registry (
                    connection_id TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'csv',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (connection_id, table_name)
                );

                CREATE TABLE IF NOT EXISTS saved_queries (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    sql TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """

    def _seed_postgres(self, connection) -> None:
        if os.getenv("APP_STORAGE_SEED_DEFAULT_CONNECTION", "false").lower() != "true":
            return

        name = os.getenv("APP_STORAGE_DEFAULT_CONNECTION_NAME", "Local Demo Postgres")
        host = os.getenv("APP_STORAGE_DEFAULT_CONNECTION_HOST", "127.0.0.1")
        port = int(os.getenv("APP_STORAGE_DEFAULT_CONNECTION_PORT", "5432"))
        database_name = os.getenv("APP_STORAGE_DEFAULT_CONNECTION_DATABASE", "ai_sql_copilot_demo")
        username = os.getenv("APP_STORAGE_DEFAULT_CONNECTION_USERNAME", "postgres")
        password_env_var = os.getenv("APP_STORAGE_DEFAULT_CONNECTION_PASSWORD_ENV_VAR")
        with self._cursor(connection) as cursor:
            cursor.execute(
                """
                INSERT INTO connection_profiles
                    (id, name, host, port, database_name, username, password_env_var)
                VALUES
                    ('default-local', %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (name, host, port, database_name, username, password_env_var),
            )

    def _translate_sql(self, sql: str) -> str:
        if self.dialect == "postgres":
            return sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        translated_sql = self._translate_sql(sql)
        normalized_params = tuple(_normalize_value(param) for param in params)
        with self.connect() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(translated_sql, normalized_params)
            connection.commit()

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        translated_sql = self._translate_sql(sql)
        normalized_params = tuple(_normalize_value(param) for param in params)
        with self.connect() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(translated_sql, normalized_params)
                row = cursor.fetchone()
        if not row:
            return None
        return {key: _normalize_row_value(key, value) for key, value in dict(row).items()}

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        translated_sql = self._translate_sql(sql)
        normalized_params = tuple(_normalize_value(param) for param in params)
        with self.connect() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(translated_sql, normalized_params)
                rows = cursor.fetchall()
        return [{key: _normalize_row_value(key, value) for key, value in dict(row).items()} for row in rows]

    def save_json(self, table: str, key_column: str, key: str, json_column: str, payload: Dict[str, Any]) -> None:
        encoded = json.dumps(payload)
        self.execute(
            f"""
            INSERT INTO {table} ({key_column}, {json_column})
            VALUES (?, ?)
            ON CONFLICT({key_column}) DO UPDATE SET
                {json_column} = excluded.{json_column},
                refreshed_at = CURRENT_TIMESTAMP
            """,
            (key, encoded),
        )

    def register_imported_dataset(self, connection_id: str, table_name: str, source_type: str) -> None:
        self.execute(
            """
            INSERT INTO imported_dataset_registry (
                connection_id, table_name, source_type, created_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(connection_id, table_name) DO UPDATE SET
                source_type = excluded.source_type,
                created_at = excluded.created_at
            """,
            (connection_id, table_name, source_type, datetime.utcnow().isoformat()),
        )

    def list_imported_datasets(self, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if connection_id:
            return self.fetchall(
                """
                SELECT connection_id, table_name, source_type, created_at
                FROM imported_dataset_registry
                WHERE connection_id = ?
                ORDER BY created_at DESC
                """,
                (connection_id,),
            )
        return self.fetchall(
            """
            SELECT connection_id, table_name, source_type, created_at
            FROM imported_dataset_registry
            ORDER BY created_at DESC
            """
        )

    def clear_imported_datasets(self, connection_id: Optional[str] = None) -> None:
        if connection_id:
            self.execute(
                "DELETE FROM imported_dataset_registry WHERE connection_id = ?",
                (connection_id,),
            )
            return
        self.execute("DELETE FROM imported_dataset_registry")
