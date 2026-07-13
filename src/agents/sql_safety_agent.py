import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class SqlSafetyResult:
    safe: bool
    risk_level: str
    warnings: List[str] = field(default_factory=list)
    suggested_fix: str = ""
    requires_confirmation: bool = False


class SQLSafetyAgent:
    destructive_commands = {"drop", "truncate", "alter", "create"}
    write_commands = {"delete", "update", "insert"}
    sensitive_terms = {
        "email",
        "phone",
        "address",
        "ssn",
        "password",
        "token",
        "api_key",
        "credit_card",
        "salary",
        "date_of_birth",
    }

    def check(self, sql: str) -> SqlSafetyResult:
        normalized = self._normalize(sql)
        first = normalized.split(" ", 1)[0] if normalized else ""
        warnings: List[str] = []

        if self._has_multiple_statements(sql):
            return SqlSafetyResult(
                safe=False,
                risk_level="dangerous",
                warnings=["Multiple SQL statements are blocked by default."],
                suggested_fix="Run one read-only statement at a time.",
                requires_confirmation=True,
            )

        if first in self.destructive_commands:
            return SqlSafetyResult(
                safe=False,
                risk_level="dangerous",
                warnings=[f"`{first.upper()}` is destructive and requires explicit confirmation."],
                suggested_fix="Run this only after confirming the exact object and impact.",
                requires_confirmation=True,
            )

        if first in self.write_commands:
            return SqlSafetyResult(
                safe=False,
                risk_level="dangerous",
                warnings=[f"`{first.upper()}` changes data and is blocked in read-only mode."],
                suggested_fix="Use a read-only SELECT query.",
                requires_confirmation=True,
            )

        if first not in {"select", "with", "explain"}:
            return SqlSafetyResult(
                safe=False,
                risk_level="dangerous",
                warnings=["Only SELECT, WITH ... SELECT, and EXPLAIN are executable by default."],
                suggested_fix="Use a read-only SQL statement.",
                requires_confirmation=True,
            )

        if first in {"select", "with"}:
            if re.search(r"\bselect\s+\*", normalized):
                warnings.append("`SELECT *` may read unnecessary or sensitive columns.")
            if " limit " not in f" {normalized} ":
                warnings.append("Query has no LIMIT and may return many rows.")
            if re.search(r"\bcross\s+join\b", normalized):
                warnings.append("CROSS JOIN can produce a very large result set.")
            if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in self.sensitive_terms):
                warnings.append("Query references columns that may contain sensitive data.")

        if warnings:
            risk = "high" if first in self.write_commands else "medium"
            return SqlSafetyResult(
                safe=first == "select",
                risk_level=risk,
                warnings=warnings,
                suggested_fix="Review warnings and add filters, explicit columns, or LIMIT where appropriate.",
                requires_confirmation=False,
            )

        return SqlSafetyResult(safe=True, risk_level="safe")

    def _normalize(self, sql: str) -> str:
        without_comments = re.sub(r"--.*?$|/\*.*?\*/", " ", sql, flags=re.MULTILINE | re.DOTALL)
        return re.sub(r"\s+", " ", without_comments).strip().lower().rstrip(";")

    def _has_multiple_statements(self, sql: str) -> bool:
        stripped = re.sub(r"--.*?$|/\*.*?\*/", " ", sql, flags=re.MULTILINE | re.DOTALL).strip()
        parts = [part.strip() for part in stripped.split(";") if part.strip()]
        return len(parts) > 1
