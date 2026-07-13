from typing import Any, Dict, List

from src.agents.result_agent import QueryResultAgent


class VisualizationService:
    def suggest(self, columns: List[str], rows: List[Dict[str, Any]]) -> str:
        return QueryResultAgent().summarize(columns, rows).visualization_suggestion
