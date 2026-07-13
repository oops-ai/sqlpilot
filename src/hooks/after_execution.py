import json
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from src.agents.result_agent import QueryResultAgent
from src.services.preference_service import PreferenceService
from src.services.query_history_service import QueryHistoryService


class AfterExecutionHook:
    def __init__(
        self,
        result_agent: QueryResultAgent = None,
        history_service: QueryHistoryService = None,
        preference_service: PreferenceService = None,
    ):
        self.result_agent = result_agent or QueryResultAgent()
        self.history_service = history_service or QueryHistoryService()
        self.preference_service = preference_service or PreferenceService()

    def run(
        self,
        sql: str,
        columns: List[str],
        rows: List[Dict[str, Any]],
        execution_time_ms: int,
        safety_level: str,
        user_request: Optional[str] = None,
        database_name: Optional[str] = None,
        tables_used: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        summary = self.result_agent.summarize(columns, rows)
        self.history_service.save(
            generated_sql=sql,
            safety_level=safety_level,
            user_request=user_request,
            executed=True,
            execution_time_ms=execution_time_ms,
            row_count=summary.row_count,
            database_name=database_name,
            tables_used=tables_used,
        )
        learned_preferences = self._learn_preferences(sql, summary.visualization_suggestion, tables_used)
        response = asdict(summary)
        response["learned_preferences"] = learned_preferences
        return response

    def _learn_preferences(
        self,
        sql: str,
        visualization_suggestion: str,
        tables_used: Optional[List[str]],
    ) -> List[str]:
        learned = []
        if visualization_suggestion and visualization_suggestion != "No visualization suggested for an empty result.":
            self.preference_service.set("last_visualization_suggestion", visualization_suggestion)
            learned.append(f"last_visualization_suggestion={visualization_suggestion}")

        limit_match = re.search(r"\blimit\s+(\d+)\b", sql, re.IGNORECASE)
        if limit_match:
            self.preference_service.set("last_limit", limit_match.group(1))
            learned.append(f"last_limit={limit_match.group(1)}")

        if tables_used:
            existing = self.preference_service.get("recent_tables")
            recent_tables = json.loads(existing) if existing else []
            for table in tables_used:
                if table in recent_tables:
                    recent_tables.remove(table)
                recent_tables.insert(0, table)
            recent_tables = recent_tables[:10]
            self.preference_service.set("recent_tables", json.dumps(recent_tables))
            learned.append(f"recent_tables={','.join(recent_tables)}")

        return learned
