from dataclasses import dataclass, field
from typing import Any, List

from src.agents.sql_safety_agent import SQLSafetyAgent
from src.database.cost_estimator import PostgresCostEstimator


@dataclass
class BeforeExecutionResult:
    query: str
    estimated_cost: str
    risk_level: str
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = False


class BeforeExecutionHook:
    def __init__(self, safety_agent: SQLSafetyAgent = None, cost_estimator: PostgresCostEstimator = None):
        self.safety_agent = safety_agent or SQLSafetyAgent()
        self.cost_estimator = cost_estimator or PostgresCostEstimator()

    def run(self, sql: str, connection: Any = None) -> BeforeExecutionResult:
        safety = self.safety_agent.check(sql)
        if not safety.safe:
            return BeforeExecutionResult(
                query=sql,
                estimated_cost="high",
                risk_level=safety.risk_level,
                warnings=safety.warnings,
                requires_confirmation=True,
            )

        estimate = self.cost_estimator.estimate(sql, connection)
        warnings = safety.warnings + estimate.warnings
        risk_level = "warning" if warnings or safety.risk_level in {"medium", "high"} else "safe"
        return BeforeExecutionResult(
            query=sql,
            estimated_cost=estimate.estimated_cost,
            risk_level=risk_level,
            warnings=warnings,
            requires_confirmation=safety.requires_confirmation,
        )
