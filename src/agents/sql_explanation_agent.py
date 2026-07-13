import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class SqlExplanation:
    what_it_does: str
    tables_used: List[str] = field(default_factory=list)
    filters: List[str] = field(default_factory=list)
    joins: List[str] = field(default_factory=list)
    performance_notes: List[str] = field(default_factory=list)


class SQLExplanationAgent:
    def explain(self, sql: str) -> SqlExplanation:
        normalized = re.sub(r"\s+", " ", sql.strip())
        lowered = normalized.lower()
        tables = re.findall(r"\bfrom\s+([a-zA-Z_][\w.]*)|\bjoin\s+([a-zA-Z_][\w.]*)", normalized, re.IGNORECASE)
        table_names = [left or right for left, right in tables]
        filters = re.findall(r"\bwhere\b\s+(.+?)(?:\bgroup\b|\border\b|\blimit\b|$)", normalized, re.IGNORECASE)
        joins = re.findall(r"\bjoin\s+([a-zA-Z_][\w.]*)\s+on\s+(.+?)(?:\bjoin\b|\bwhere\b|\bgroup\b|\border\b|\blimit\b|$)", normalized, re.IGNORECASE)

        notes: List[str] = []
        if "select *" in lowered:
            notes.append("SELECT * can read more data than needed.")
        if lowered.startswith("select") and " limit " not in f" {lowered} ":
            notes.append("No LIMIT is present, so exploratory use may return many rows.")
        if "group by" in lowered:
            notes.append("GROUP BY may be expensive on large tables without supporting indexes or filters.")

        what = "This query reads data"
        if table_names:
            what += f" from {', '.join(table_names)}"
        if "group by" in lowered:
            what += ", groups rows, and returns aggregated results"
        what += "."

        return SqlExplanation(
            what_it_does=what,
            tables_used=table_names,
            filters=[item.strip() for item in filters],
            joins=[f"{table} ON {condition.strip()}" for table, condition in joins],
            performance_notes=notes,
        )
