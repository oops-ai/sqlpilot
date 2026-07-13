import time
from dataclasses import dataclass
from typing import Any, Dict, List

from src.config import Settings, get_settings
from src.agents.sql_safety_agent import SQLSafetyAgent


@dataclass
class QueryExecutionResult:
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int


class QueryExecutor:
    def __init__(self, safety_agent: SQLSafetyAgent = None, settings: Settings = None):
        self.safety_agent = safety_agent or SQLSafetyAgent()
        self.settings = settings or get_settings()

    def execute(self, sql: str, connection: Any, confirmed: bool = False) -> QueryExecutionResult:
        safety = self.safety_agent.check(sql)
        if not safety.safe:
            raise PermissionError("Unsafe query blocked before execution.")

        started = time.perf_counter()
        try:
            with connection.cursor() as cursor:
                if self.settings.read_only_execution:
                    cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(f"SET LOCAL statement_timeout = {int(self.settings.statement_timeout_ms)}")
                cursor.execute(sql)
                if cursor.description:
                    columns = [getattr(column, "name", column[0]) for column in cursor.description]
                    raw_rows = cursor.fetchall()
                    rows = [dict(zip(columns, row)) for row in raw_rows]
                else:
                    columns = []
                    rows = []
                connection.commit()
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return QueryExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
        )
