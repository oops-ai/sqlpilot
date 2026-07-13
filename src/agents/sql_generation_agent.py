from dataclasses import dataclass, field
import json
import re
from typing import List, Optional

from src.database.schema_loader import DatabaseSchema, TableInfo
from src.services.llm_service import LLMService, build_sql_generation_prompt, parse_llm_json_response

try:
    import sqlglot
    from sqlglot import expressions as exp
except ImportError as exc:  # pragma: no cover - dependency issue
    raise RuntimeError("Install sqlglot to use SQL generation validation.") from exc


@dataclass
class SqlGenerationResult:
    sql: str
    explanation: str
    safety_notes: List[str] = field(default_factory=list)


class SQLGenerationAgent:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service

    def generate(
        self,
        natural_language_request: str,
        schema: Optional[DatabaseSchema] = None,
        default_limit: int = 100,
        preferred_table_name: Optional[str] = None,
    ) -> SqlGenerationResult:
        if not schema or not schema.tables:
            return SqlGenerationResult(
                sql="-- Schema is required to generate accurate SQL.",
                explanation="I need database schema context before generating SQL so table and column names are not invented.",
                safety_notes=["No SQL was generated because schema context is missing."],
            )

        requested_limit = self._requested_limit(natural_language_request)
        effective_limit = requested_limit or default_limit
        table = schema.find_table_for_request(natural_language_request, preferred_table_name=preferred_table_name)

        if table and preferred_table_name and self._is_generic_row_request(natural_language_request):
            request = natural_language_request.lower()
            return SqlGenerationResult(
                sql=self._build_select(request, table, effective_limit),
                explanation=f"Reads from `{table.name}` using schema-known columns and returns a limited result for review.",
                safety_notes=["Exploratory SELECT includes a LIMIT."],
            )

        if self.llm_service:
            llm_result = self._generate_with_llm(
                natural_language_request,
                schema,
                effective_limit,
                requested_limit=requested_limit,
            )
            if llm_result:
                return llm_result

        if not table:
            return SqlGenerationResult(
                sql="-- No matching table found in schema.",
                explanation="No table in the schema matched the request.",
                safety_notes=["Review schema context and try again."],
            )

        request = natural_language_request.lower()
        sql = self._build_select(request, table, effective_limit)
        return SqlGenerationResult(
            sql=sql,
            explanation=f"Reads from `{table.name}` using schema-known columns and returns a limited result for review.",
            safety_notes=["Exploratory SELECT includes a LIMIT."],
        )

    def _build_select(self, request: str, table: TableInfo, default_limit: int) -> str:
        columns = table.column_names()
        if not columns:
            return f"SELECT\n    *\nFROM {table.name}\nLIMIT {default_limit};"

        date_column = self._first_matching_column(columns, ("date", "created_at", "order_date", "month"))
        amount_column = self._first_matching_column(columns, ("amount", "total", "revenue", "sales", "price"))

        if any(word in request for word in ("total", "sum", "revenue", "sales")) and amount_column:
            if "month" in request and date_column:
                return (
                    "SELECT\n"
                    f"    DATE_TRUNC('month', {date_column}) AS month,\n"
                    f"    SUM({amount_column}) AS total_{amount_column}\n"
                    f"FROM {table.name}\n"
                    f"GROUP BY DATE_TRUNC('month', {date_column})\n"
                    "ORDER BY month\n"
                    f"LIMIT {default_limit};"
                )
            return (
                "SELECT\n"
                f"    SUM({amount_column}) AS total_{amount_column}\n"
                f"FROM {table.name};"
            )

        selected = columns[: min(5, len(columns))]
        select_list = ",\n    ".join(selected)
        return f"SELECT\n    {select_list}\nFROM {table.name}\nLIMIT {default_limit};"

    def _first_matching_column(self, columns: List[str], names: tuple) -> Optional[str]:
        lower_to_original = {column.lower(): column for column in columns}
        for wanted in names:
            if wanted in lower_to_original:
                return lower_to_original[wanted]
        for column in columns:
            if any(wanted in column.lower() for wanted in names):
                return column
        return None

    def _generate_with_llm(
        self,
        natural_language_request: str,
        schema: DatabaseSchema,
        default_limit: int,
        requested_limit: Optional[int] = None,
    ) -> Optional[SqlGenerationResult]:
        prompt = build_sql_generation_prompt(natural_language_request, schema, default_limit)
        try:
            payload = parse_llm_json_response(self.llm_service.complete(prompt))
        except Exception:
            return None

        sql = str(payload.get("sql", "")).strip()
        if not sql or not self._is_valid_sql(sql):
            return None
        if not self._uses_known_identifiers(sql, schema):
            return SqlGenerationResult(
                sql="-- Generated SQL referenced unknown schema identifiers.",
                explanation="The local model produced SQL that did not match the loaded schema.",
                safety_notes=["No SQL was returned for execution."],
            )
        sql = self._ensure_limit_for_exploratory_select(sql, default_limit)
        if requested_limit is not None:
            sql = self._enforce_limit(sql, requested_limit)
        return SqlGenerationResult(
            sql=sql,
            explanation=str(payload.get("explanation", "Generated from local schema context.")),
            safety_notes=list(payload.get("safety_notes", [])),
        )

    def _is_valid_sql(self, sql: str) -> bool:
        try:
            sqlglot.parse_one(sql, read="postgres")
            return True
        except Exception:
            return False

    def _uses_known_identifiers(self, sql: str, schema: DatabaseSchema) -> bool:
        known_tables = {name.lower() for name in schema.table_names()}
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception:
            return False

        table_aliases = {}
        table_columns = {
            table_name.lower(): {column.lower() for column in table.column_names()}
            for table_name, table in schema.tables.items()
        }
        all_schema_columns = {
            column.lower()
            for table in schema.tables.values()
            for column in table.column_names()
        }

        for table in parsed.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name not in known_tables:
                return False
            table_aliases[table_name] = table_name
            if table.alias:
                table_aliases[table.alias.lower()] = table_name

        if not table_aliases:
            return False

        output_aliases = {
            alias.alias.lower()
            for alias in parsed.find_all(exp.Alias)
            if alias.alias
        }

        for column in parsed.find_all(exp.Column):
            column_name = column.name.lower()
            table_qualifier = column.table.lower() if column.table else ""

            if table_qualifier:
                source_table = table_aliases.get(table_qualifier)
                if not source_table or column_name not in table_columns.get(source_table, set()):
                    return False
                continue

            if column_name in output_aliases:
                continue
            if column_name not in all_schema_columns:
                return False

        return True

    def _ensure_limit_for_exploratory_select(self, sql: str, default_limit: int) -> str:
        normalized = re.sub(r"\s+", " ", sql.strip()).lower()
        if normalized.startswith("select") and " limit " not in f" {normalized} " and "group by" not in normalized:
            return sql.rstrip(";") + f"\nLIMIT {default_limit};"
        return sql

    def _enforce_limit(self, sql: str, limit_value: int) -> str:
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception:
            return sql

        if not isinstance(parsed, exp.Select):
            return sql

        parsed.set("limit", exp.Limit(expression=exp.Literal.number(limit_value)))
        return parsed.sql(dialect="postgres")

    def _requested_limit(self, request: str) -> Optional[int]:
        lowered = request.lower()
        if any(token in lowered for token in ("all rows", "full dataset", "everything", "without limit")):
            return None
        patterns = [
            r"\btop\s+(\d+)\b",
            r"\bfirst\s+(\d+)\b",
            r"\blimit\s+(\d+)\b",
            r"\bshow\s+(\d+)\s+rows\b",
            r"\b(\d+)\s+rows\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                try:
                    value = int(match.group(1))
                    return value if value > 0 else None
                except ValueError:
                    continue
        return None

    def _is_generic_row_request(self, request: str) -> bool:
        lowered = request.lower()
        row_request_tokens = (
            "top ",
            "first ",
            "rows",
            "row",
            "show ",
            "list ",
        )
        return any(token in lowered for token in row_request_tokens) and self._requested_limit(request) is not None
