from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CostEstimate:
    estimated_cost: str
    warnings: List[str] = field(default_factory=list)
    raw_plan: Optional[Dict[str, Any]] = None


class PostgresCostEstimator:
    def estimate(self, sql: str, connection: Any = None) -> CostEstimate:
        if connection is None:
            return CostEstimate(
                estimated_cost="medium",
                warnings=["No database connection was provided, so cost was estimated with static checks only."],
            )

        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}")
            plan_payload = cursor.fetchone()[0]
        try:
            connection.rollback()
        except Exception:
            pass

        root = plan_payload[0]["Plan"] if isinstance(plan_payload, list) else plan_payload["Plan"]
        total_cost = float(root.get("Total Cost", 0))
        estimated_rows = int(root.get("Plan Rows", 0))
        warnings = []

        if total_cost > 100000 or estimated_rows > 1000000:
            level = "high"
        elif total_cost > 10000 or estimated_rows > 100000:
            level = "medium"
        else:
            level = "low"

        plan_text = str(root).lower()
        if "seq scan" in plan_text:
            warnings.append("Query plan includes a sequential scan.")
        if "nested loop" in plan_text:
            warnings.append("Query plan includes a nested loop join.")
        if estimated_rows > 100000:
            warnings.append("Query may scan or return a large number of rows.")

        return CostEstimate(estimated_cost=level, warnings=warnings, raw_plan=root)
