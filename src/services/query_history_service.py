import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from src.services.app_storage import AppStorage


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


@dataclass
class QueryHistoryEntry:
    id: str
    user_request: Optional[str]
    generated_sql: str
    executed: bool
    execution_time_ms: Optional[int]
    row_count: Optional[int]
    database_name: Optional[str]
    tables_used: List[str]
    safety_level: str
    created_at: datetime


class QueryHistoryService:
    def __init__(self, storage: Optional[AppStorage] = None):
        self.storage = storage
        self._entries: List[QueryHistoryEntry] = []

    def save(
        self,
        generated_sql: str,
        safety_level: str,
        user_request: Optional[str] = None,
        executed: bool = False,
        execution_time_ms: Optional[int] = None,
        row_count: Optional[int] = None,
        database_name: Optional[str] = None,
        tables_used: Optional[List[str]] = None,
    ) -> QueryHistoryEntry:
        entry = QueryHistoryEntry(
            id=str(uuid4()),
            user_request=user_request,
            generated_sql=generated_sql,
            executed=executed,
            execution_time_ms=execution_time_ms,
            row_count=row_count,
            database_name=database_name,
            tables_used=tables_used or [],
            safety_level=safety_level,
            created_at=datetime.utcnow(),
        )
        if self.storage:
            self.storage.execute(
                """
                INSERT INTO query_history (
                    id, user_request, generated_sql, executed, execution_time_ms,
                    row_count, database_name, tables_used_json, safety_level, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.user_request,
                    entry.generated_sql,
                    1 if entry.executed else 0,
                    entry.execution_time_ms,
                    entry.row_count,
                    entry.database_name,
                    json.dumps(entry.tables_used),
                    entry.safety_level,
                    entry.created_at.isoformat(),
                ),
            )
        else:
            self._entries.append(entry)
        return entry

    def list_recent(self, limit: int = 50) -> List[QueryHistoryEntry]:
        if self.storage:
            rows = self.storage.fetchall(
                """
                SELECT *
                FROM query_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [
                QueryHistoryEntry(
                    id=row["id"],
                    user_request=row["user_request"],
                    generated_sql=row["generated_sql"],
                    executed=bool(row["executed"]),
                    execution_time_ms=row["execution_time_ms"],
                    row_count=row["row_count"],
                    database_name=row["database_name"],
                    tables_used=row["tables_used_json"] if isinstance(row["tables_used_json"], list) else json.loads(row["tables_used_json"]),
                    safety_level=row["safety_level"],
                    created_at=_parse_datetime(row["created_at"]),
                )
                for row in rows
            ]
        return list(reversed(self._entries[-limit:]))
