from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List


@dataclass
class QueryResultSummary:
    summary: str
    row_count: int
    visualization_suggestion: str
    follow_up_questions: List[str] = field(default_factory=list)
    learned_preferences: List[str] = field(default_factory=list)


class QueryResultAgent:
    def summarize(self, columns: List[str], rows: List[Dict[str, Any]]) -> QueryResultSummary:
        row_count = len(rows)
        date_columns = self._date_columns(columns, rows)
        has_date = bool(date_columns)
        numeric_columns = self._numeric_columns(columns, rows)
        category_columns = [column for column in columns if column not in numeric_columns]

        if row_count == 0:
            visualization = "No visualization suggested for an empty result."
            follow_ups = ["Check filters and date ranges.", "Confirm the target table contains matching rows."]
        elif has_date and numeric_columns:
            visualization = "Line chart"
            follow_ups = ["Compare this trend with the previous period."]
        elif category_columns and numeric_columns:
            visualization = "Bar chart"
            follow_ups = ["Show the top categories by this metric."]
        else:
            visualization = "Table"
            follow_ups = ["Filter or sort the result for deeper inspection."]

        return QueryResultSummary(
            summary=f"Query returned {row_count} row{'s' if row_count != 1 else ''}.",
            row_count=row_count,
            visualization_suggestion=visualization,
            follow_up_questions=follow_ups,
        )

    def _numeric_columns(self, columns: List[str], rows: List[Dict[str, Any]]) -> List[str]:
        numeric = []
        for column in columns:
            values = [row.get(column) for row in rows if row.get(column) is not None]
            if values and all(self._is_numeric_value(value) for value in values):
                numeric.append(column)
        return numeric

    def _date_columns(self, columns: List[str], rows: List[Dict[str, Any]]) -> List[str]:
        date_columns = []
        for column in columns:
            lower = column.lower()
            values = [row.get(column) for row in rows if row.get(column) is not None]
            name_looks_temporal = any(token in lower for token in ("date", "time", "month", "year", "day"))
            value_looks_temporal = bool(values) and all(self._is_date_value(value) for value in values)
            if name_looks_temporal or value_looks_temporal:
                date_columns.append(column)
        return date_columns

    def _is_numeric_value(self, value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float, Decimal)):
            return True
        if isinstance(value, str):
            try:
                Decimal(value)
                return True
            except Exception:
                return False
        return False

    def _is_date_value(self, value: Any) -> bool:
        if isinstance(value, (datetime, date)):
            return True
        if not isinstance(value, str):
            return False
        normalized = value.strip()
        if not normalized:
            return False
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            datetime.fromisoformat(normalized)
            return True
        except ValueError:
            return False
