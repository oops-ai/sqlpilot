import json
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.api.routes import ApiHandlers


SUPPORTED_PROTOCOL_VERSION = "2024-11-05"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]


def _tool_schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


class SqlMcpServer:
    def __init__(self, handlers: Optional[ApiHandlers] = None):
        self.handlers = handlers or ApiHandlers(use_llm=True)
        self.tools = self._build_tools()

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize":
            return self._response(
                request_id,
                {
                    "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
                    "serverInfo": {"name": "ai-sql-copilot-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return self._response(
                request_id,
                {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self.tools
                    ]
                },
            )

        if method == "tools/call":
            params = message.get("params") or {}
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            return self._call_tool(request_id, tool_name, arguments)

        return self._error(request_id, -32601, f"Method not found: {method}")

    def _build_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                "list_connections",
                "List saved database connections.",
                _tool_schema({}),
            ),
            ToolSpec(
                "generate_sql",
                "Generate SQL from natural language and schema context.",
                _tool_schema(
                    {
                        "natural_language_request": {"type": "string"},
                        "connection_id": {"type": "string"},
                    },
                    ["natural_language_request"],
                ),
            ),
            ToolSpec(
                "explain_sql",
                "Explain a SQL query in plain language.",
                _tool_schema({"sql": {"type": "string"}}, ["sql"]),
            ),
            ToolSpec(
                "optimize_sql",
                "Optimize a SQL query using schema and cost hints.",
                _tool_schema(
                    {
                        "sql": {"type": "string"},
                        "connection_id": {"type": "string"},
                    },
                    ["sql"],
                ),
            ),
            ToolSpec(
                "check_safety",
                "Check a SQL query for risk before execution.",
                _tool_schema({"sql": {"type": "string"}}, ["sql"]),
            ),
            ToolSpec(
                "refresh_schema",
                "Refresh the cached schema for a saved connection.",
                _tool_schema({"connection_id": {"type": "string"}}, ["connection_id"]),
            ),
            ToolSpec(
                "get_schema",
                "Read the cached schema for a saved connection.",
                _tool_schema({"connection_id": {"type": "string"}}, ["connection_id"]),
            ),
            ToolSpec(
                "infer_join",
                "Infer a join condition between two tables.",
                _tool_schema(
                    {
                        "connection_id": {"type": "string"},
                        "left_table": {"type": "string"},
                        "right_table": {"type": "string"},
                    },
                    ["connection_id", "left_table", "right_table"],
                ),
            ),
            ToolSpec(
                "query_history",
                "List recent generated or executed queries.",
                _tool_schema({"limit": {"type": "integer", "minimum": 1}}),
            ),
            ToolSpec(
                "execute_sql",
                "Execute SQL against the connected database or app metadata database.",
                _tool_schema(
                    {
                        "database": {"type": "string", "enum": ["target", "app"]},
                        "sql": {"type": "string"},
                        "connection_id": {"type": "string"},
                        "confirmed": {"type": "boolean", "default": False},
                    },
                    ["database", "sql"],
                ),
            ),
        ]

    def _call_tool(self, request_id: Any, name: Any, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "list_connections":
                payload = self.handlers.list_connections()
            elif name == "generate_sql":
                payload = self.handlers.generate_sql(
                    self._request_model("GenerateSqlRequest", arguments)
                )
            elif name == "explain_sql":
                payload = self.handlers.explain_sql(self._request_model("ExplainSqlRequest", arguments))
            elif name == "optimize_sql":
                payload = self.handlers.optimize_sql(self._request_model("OptimizeSqlRequest", arguments))
            elif name == "check_safety":
                payload = self.handlers.check_safety(self._request_model("CheckSafetyRequest", arguments))
            elif name == "refresh_schema":
                payload = self.handlers.refresh_schema(self._request_model("SchemaRefreshRequest", arguments))
            elif name == "get_schema":
                payload = self.handlers.get_schema(arguments.get("connection_id", ""))
            elif name == "infer_join":
                payload = self.handlers.infer_join(self._request_model("InferJoinRequest", arguments))
            elif name == "query_history":
                limit = int(arguments.get("limit", 50) or 50)
                payload = self.handlers.query_history()[:limit]
            elif name == "execute_sql":
                payload = self._execute_sql(arguments)
            else:
                return self._error(request_id, -32601, f"Unknown tool: {name}")
        except Exception as exc:
            return self._error(request_id, -32000, str(exc))

        return self._response(request_id, {"content": [{"type": "text", "text": json.dumps(payload, default=str, indent=2)}]})

    def _execute_sql(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        database = arguments.get("database")
        sql = str(arguments.get("sql", "")).strip()
        confirmed = bool(arguments.get("confirmed", False))
        if not sql:
            raise ValueError("sql is required")

        safety = self.handlers.safety_agent.check(sql)
        if _is_read_only_sql(sql):
            if database == "target":
                connection_id = arguments.get("connection_id", "")
                if not connection_id:
                    raise ValueError("connection_id is required for target database queries")
                return self._execute_target_read(sql, connection_id)
            if database == "app":
                return self._execute_app_read(sql)
            raise ValueError("database must be target or app")

        if not confirmed:
            return {
                "blocked": True,
                "reason": "Confirmation required for mutating SQL.",
                "safety": safety.__dict__,
            }

        if database == "target":
            connection_id = arguments.get("connection_id", "")
            if not connection_id:
                raise ValueError("connection_id is required for target database queries")
            return self._execute_target_write(sql, connection_id)
        if database == "app":
            return self._execute_app_write(sql)
        raise ValueError("database must be target or app")

    def _execute_target_read(self, sql: str, connection_id: str) -> Dict[str, Any]:
        return self._run_target_query(sql, connection_id, read_only=True)

    def _execute_target_write(self, sql: str, connection_id: str) -> Dict[str, Any]:
        return self._run_target_query(sql, connection_id, read_only=False)

    def _execute_app_read(self, sql: str) -> Dict[str, Any]:
        return self._run_app_query(sql, read_only=True)

    def _execute_app_write(self, sql: str) -> Dict[str, Any]:
        return self._run_app_query(sql, read_only=False)

    def _run_target_query(self, sql: str, connection_id: str, read_only: bool) -> Dict[str, Any]:
        connection = self.handlers.connection_service.connect(connection_id)
        try:
            with self._cursor(connection) as cursor:
                if read_only:
                    cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(f"SET LOCAL statement_timeout = {int(self.handlers.settings.statement_timeout_ms)}")
                cursor.execute(sql)
                if cursor.description:
                    columns = [getattr(column, "name", column[0]) for column in cursor.description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
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
        finally:
            connection.close()
        return {"columns": columns, "rows": rows, "row_count": len(rows)}

    def _run_app_query(self, sql: str, read_only: bool) -> Dict[str, Any]:
        connection = self.handlers.storage.connect()
        try:
            with self._cursor(connection) as cursor:
                if getattr(self.handlers.storage, "dialect", "sqlite") == "postgres":
                    if read_only:
                        cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(f"SET LOCAL statement_timeout = {int(self.handlers.settings.statement_timeout_ms)}")
                cursor.execute(sql)
                if cursor.description:
                    columns = [getattr(column, "name", column[0]) for column in cursor.description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
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
        finally:
            connection.close()
        return {"columns": columns, "rows": rows, "row_count": len(rows)}

    @contextmanager
    def _cursor(self, connection):
        cursor = connection.cursor()
        try:
            yield cursor
        finally:
            close = getattr(cursor, "close", None)
            if close:
                close()

    def _request_model(self, name: str, arguments: Dict[str, Any]):
        from src.api import schemas

        model = getattr(schemas, name)
        return model(**arguments)

    def _response(self, request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _is_read_only_sql(sql: str) -> bool:
    normalized = re.sub(r"\s+", " ", sql.strip()).lower()
    return normalized.startswith(("select", "with", "explain"))


def run_stdio() -> None:
    server = SqlMcpServer()
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        response = server.handle(message)
        if response is not None:
            print(json.dumps(response), flush=True)


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()
