from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DatabaseConfig:
    dsn: str


class PostgresConnectionFactory:
    def __init__(self, config: DatabaseConfig):
        self.config = config

    def connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install psycopg to connect to PostgreSQL.") from exc
        return psycopg.connect(self.config.dsn)
