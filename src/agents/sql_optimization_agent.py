import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SqlOptimizationResult:
    issues_found: List[str] = field(default_factory=list)
    optimized_query: str = ""
    why_this_is_better: List[str] = field(default_factory=list)
    index_suggestions: List[str] = field(default_factory=list)


class SQLOptimizationAgent:
    def optimize(self, sql: str, plan: Optional[Dict[str, Any]] = None) -> SqlOptimizationResult:
        normalized = re.sub(r"\s+", " ", sql.strip())
        lowered = normalized.lower()
        issues: List[str] = []
        improvements: List[str] = []
        indexes: List[str] = []
        optimized = sql.strip()

        if "select *" in lowered:
            issues.append("Query uses SELECT *.")
            improvements.append("Selecting explicit columns reduces I/O and avoids exposing unnecessary data.")

        if lowered.startswith("select") and " limit " not in f" {lowered} " and "group by" not in lowered:
            issues.append("Exploratory SELECT has no LIMIT.")
            optimized = optimized.rstrip(";") + "\nLIMIT 100;"
            improvements.append("LIMIT bounds the amount of data returned during exploration.")

        where_match = re.search(r"\bwhere\b\s+(.+?)(?:\border\b|\bgroup\b|\blimit\b|$)", normalized, re.IGNORECASE)
        if where_match:
            filter_columns = re.findall(r"([a-zA-Z_][\w.]*)\s*(?:=|>|<|>=|<=|between|in\b)", where_match.group(1), re.IGNORECASE)
            for column in filter_columns:
                indexes.append(f"Consider an index on `{column}` if this filter is common and selective.")

        if re.search(r"\bwhere\b\s+\w+\s*\(", lowered):
            issues.append("Function call in WHERE may prevent index use.")
            improvements.append("Filtering without wrapping indexed columns helps PostgreSQL use indexes.")

        if plan:
            self._analyze_plan(plan, issues, improvements, indexes)

        if not issues:
            improvements.append("No obvious SQL anti-patterns were found by static analysis.")

        return SqlOptimizationResult(
            issues_found=issues,
            optimized_query=optimized,
            why_this_is_better=improvements,
            index_suggestions=indexes,
        )

    def _analyze_plan(
        self,
        plan: Dict[str, Any],
        issues: List[str],
        improvements: List[str],
        indexes: List[str],
    ) -> None:
        for node in self._walk_plan(plan):
            node_type = str(node.get("Node Type", ""))
            relation = node.get("Relation Name")
            estimated_rows = int(node.get("Plan Rows", 0) or 0)

            if node_type == "Seq Scan" and relation:
                issues.append(f"Query plan uses a sequential scan on `{relation}`.")
                filter_text = node.get("Filter") or node.get("Index Cond") or ""
                columns = self._columns_from_plan_expression(str(filter_text))
                if columns:
                    for column in columns:
                        indexes.append(f"Consider an index on `{relation}.{column}` for this filter.")
                else:
                    improvements.append(f"Add a selective WHERE clause or supporting index for `{relation}` if the table is large.")

            if node_type == "Nested Loop" and estimated_rows > 10000:
                issues.append("Query plan uses a nested loop with a high estimated row count.")
                improvements.append("A better join filter or index on join keys may reduce repeated scans.")

            if node_type == "Sort" and estimated_rows > 10000:
                issues.append("Query plan sorts a large estimated result set.")
                improvements.append("Add a LIMIT, reduce rows earlier, or consider an index matching the ORDER BY.")

            if node_type in {"Aggregate", "HashAggregate"} and estimated_rows > 10000:
                issues.append("Query plan aggregates a large estimated result set.")
                improvements.append("Filter rows before aggregation when possible.")

    def _walk_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        nodes = [plan]
        for child in plan.get("Plans", []) or []:
            nodes.extend(self._walk_plan(child))
        return nodes

    def _columns_from_plan_expression(self, expression: str) -> List[str]:
        candidates = re.findall(r"\b([a-zA-Z_][\w]*)\b\s*(?:=|>|<|>=|<=|~~|LIKE|IN)", expression, re.IGNORECASE)
        ignored = {"and", "or", "not", "null", "true", "false"}
        return [candidate for candidate in candidates if candidate.lower() not in ignored]
