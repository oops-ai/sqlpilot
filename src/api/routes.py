from dataclasses import asdict, is_dataclass
import os
from typing import Optional

from src.agents.sql_explanation_agent import SQLExplanationAgent
from src.agents.sql_generation_agent import SQLGenerationAgent
from src.agents.sql_optimization_agent import SQLOptimizationAgent
from src.agents.sql_safety_agent import SQLSafetyAgent
from src.api.schemas import (
    AskDatabaseRequest,
    AskDatabaseResponse,
    CheckSafetyRequest,
    ConnectionCreateRequest,
    ExecuteQueryRequest,
    ExplainSqlRequest,
    GenerateSqlRequest,
    InferJoinRequest,
    ImportDatasetRequest,
    OptimizeSqlRequest,
    SchemaRefreshRequest,
)
from src.config import get_settings
from src.database.query_executor import QueryExecutor
from src.database.cost_estimator import PostgresCostEstimator
from src.database.schema_loader import DatabaseSchema
from src.hooks.before_execution import BeforeExecutionHook
from src.hooks.after_execution import AfterExecutionHook
from src.services.app_storage import AppStorage
from src.services.dataset_import_service import DatasetImportService
from src.services.connection_service import ConnectionService
from src.services.llm_service import OllamaLLMService
from src.services.query_history_service import QueryHistoryService
from src.services.schema_service import SchemaService
from src.services.join_inference_service import JoinInferenceService
from src.services.preference_service import PreferenceService
from src.services.realtime_service import RealtimeService


class ApiHandlers:
    def __init__(
        self,
        schema: Optional[DatabaseSchema] = None,
        history: QueryHistoryService = None,
        storage: AppStorage = None,
        use_llm: bool = False,
    ):
        self.settings = get_settings()
        self.storage = storage or AppStorage(self.settings.app_database_url)
        self.connection_service = ConnectionService(self.storage)
        self.schema_service = SchemaService(self.storage, self.connection_service)
        self.schema = schema or DatabaseSchema()
        self.history = history or QueryHistoryService(self.storage)
        self.preference_service = PreferenceService(self.storage)
        llm_service = OllamaLLMService(self.settings) if use_llm and self.settings.use_local_llm else None
        self.generation_agent = SQLGenerationAgent(llm_service=llm_service)
        self.explanation_agent = SQLExplanationAgent()
        self.optimization_agent = SQLOptimizationAgent()
        self.safety_agent = SQLSafetyAgent()
        self.before_execution_hook = BeforeExecutionHook(self.safety_agent)
        self.cost_estimator = PostgresCostEstimator()
        self.query_executor = QueryExecutor(self.safety_agent, self.settings)
        self.after_execution_hook = AfterExecutionHook(history_service=self.history, preference_service=self.preference_service)
        self.join_inference_service = JoinInferenceService()
        self.realtime_service = RealtimeService(self.connection_service)
        self.dataset_import_service = DatasetImportService(
            self.connection_service,
            self.schema_service,
            self.preference_service,
        )

    def create_connection(self, request: ConnectionCreateRequest) -> dict:
        profile = self.connection_service.create(
            name=request.name,
            host=request.host,
            port=request.port,
            database_name=request.database_name,
            username=request.username,
            password_env_var=request.password_env_var or None,
        )
        return _to_dict(profile)

    def list_connections(self) -> list:
        return [_to_dict(profile) for profile in self.connection_service.list()]

    def test_connection(self, connection_id: str) -> dict:
        return {"ok": self.connection_service.test(connection_id)}

    def refresh_schema(self, request: SchemaRefreshRequest) -> dict:
        schema = self.schema_service.refresh(request.connection_id)
        return schema.to_dict()

    def get_schema(self, connection_id: str) -> dict:
        schema = self.schema_service.get(connection_id)
        return schema.to_dict() if schema else {"tables": {}}

    def infer_join(self, request: InferJoinRequest) -> list:
        schema = self.schema_service.get(request.connection_id)
        if not schema:
            return []
        return [_to_dict(candidate) for candidate in self.join_inference_service.infer(schema, request.left_table, request.right_table)]

    def import_dataset(self, request: ImportDatasetRequest) -> dict:
        imported = self.dataset_import_service.import_dataset(
            request.connection_id,
            csv_text=request.csv_text,
            source_url=request.source_url,
            file_name=request.file_name,
            table_name=request.table_name,
            replace=request.replace,
        )
        payload = _to_dict(imported)
        payload["imported_schema"] = payload.pop("schema")
        return payload

    def ask_database(self, request: AskDatabaseRequest) -> dict:
        schema = self.schema_service.get(request.connection_id) or self.schema
        preferred_table = self._preferred_table(schema)
        generated = self.generation_agent.generate(
            request.natural_language_request,
            schema,
            default_limit=self.settings.default_limit,
            preferred_table_name=preferred_table.name if preferred_table else None,
        )
        safety = self.safety_agent.check(generated.sql)
        if not safety.safe:
            return {
                "sql": generated.sql,
                "explanation": generated.explanation,
                "safety": _to_dict(safety),
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": 0,
                "summary": "Query blocked by safety checks.",
                "visualization_suggestion": "",
            }

        try:
            return self._execute_answer_query(
                request=request,
                sql=generated.sql,
                explanation=generated.explanation,
                safety=safety,
            )
        except Exception:
            fallback_sql = self._fallback_sql(request.natural_language_request, schema, generated.sql)
            fallback_explanation = "Used a safe fallback query because the first draft could not run cleanly."
            fallback_safety = self.safety_agent.check(fallback_sql)
            try:
                return self._execute_answer_query(
                    request=request,
                    sql=fallback_sql,
                    explanation=fallback_explanation,
                    safety=fallback_safety,
                )
            except Exception as exc:
                return {
                    "sql": fallback_sql,
                    "explanation": fallback_explanation,
                    "safety": _to_dict(fallback_safety),
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "execution_time_ms": 0,
                    "summary": f"Could not answer the question cleanly: {exc}",
                    "visualization_suggestion": "",
                }

    def generate_sql(self, request: GenerateSqlRequest) -> dict:
        schema = self.schema_service.get(request.connection_id) if request.connection_id else self.schema
        preferred_table = self._preferred_table(schema) if schema else None
        result = self.generation_agent.generate(
            request.natural_language_request,
            schema,
            default_limit=self.settings.default_limit,
            preferred_table_name=preferred_table.name if preferred_table else None,
        )
        safety = self.safety_agent.check(result.sql)
        if result.sql and not result.sql.startswith("--"):
            self.history.save(
                generated_sql=result.sql,
                safety_level=safety.risk_level,
                user_request=request.natural_language_request,
                executed=False,
            )
        return _to_dict(result)

    def explain_sql(self, request: ExplainSqlRequest) -> dict:
        return _to_dict(self.explanation_agent.explain(request.sql))

    def optimize_sql(self, request: OptimizeSqlRequest) -> dict:
        plan = None
        connection = self.connection_service.connect(request.connection_id) if request.connection_id else None
        try:
            if connection:
                safety = self.safety_agent.check(request.sql)
                if safety.safe:
                    plan = self.cost_estimator.estimate(request.sql, connection).raw_plan
            return _to_dict(self.optimization_agent.optimize(request.sql, plan=plan))
        finally:
            if connection:
                connection.close()

    def check_safety(self, request: CheckSafetyRequest) -> dict:
        return _to_dict(self.safety_agent.check(request.sql))

    def before_execution(self, request: CheckSafetyRequest) -> dict:
        connection = self.connection_service.connect(request.connection_id) if request.connection_id else None
        try:
            return _to_dict(self.before_execution_hook.run(request.sql, connection))
        finally:
            if connection:
                connection.close()

    def execute_query(self, request: ExecuteQueryRequest) -> dict:
        connection = self.connection_service.connect(request.connection_id)
        try:
            before = self.before_execution_hook.run(request.sql, connection)
            if before.risk_level == "dangerous":
                raise PermissionError("Unsafe query blocked before execution.")
            execution = self.query_executor.execute(request.sql, connection, confirmed=request.confirmed)
        finally:
            connection.close()
        after = self.after_execution_hook.run(
            sql=request.sql,
            columns=execution.columns,
            rows=execution.rows,
            execution_time_ms=execution.execution_time_ms,
            safety_level=before.risk_level,
            user_request=request.user_request,
        )
        return {
            "columns": execution.columns,
            "rows": execution.rows,
            "row_count": execution.row_count,
            "execution_time_ms": execution.execution_time_ms,
            "summary": after["summary"],
            "visualization_suggestion": after["visualization_suggestion"],
        }

    def query_history(self) -> list:
        return [_to_dict(entry) for entry in self.history.list_recent()]

    def cleanup_session(self) -> list:
        return self.dataset_import_service.cleanup_imported_datasets()

    def _execute_answer_query(self, request, sql: str, explanation: str, safety) -> dict:
        connection = self.connection_service.connect(request.connection_id)
        try:
            before = self.before_execution_hook.run(sql, connection)
            if before.risk_level == "dangerous":
                raise PermissionError("Unsafe query blocked before execution.")
            execution = self.query_executor.execute(sql, connection, confirmed=True)
        finally:
            connection.close()

        after = self.after_execution_hook.run(
            sql=sql,
            columns=execution.columns,
            rows=execution.rows,
            execution_time_ms=execution.execution_time_ms,
            safety_level=before.risk_level,
            user_request=request.natural_language_request,
        )
        return {
            "sql": sql,
            "explanation": explanation,
            "safety": _to_dict(safety),
            "columns": execution.columns,
            "rows": execution.rows,
            "row_count": execution.row_count,
            "execution_time_ms": execution.execution_time_ms,
            "summary": after["summary"],
            "visualization_suggestion": after["visualization_suggestion"],
        }

    def _fallback_sql(self, request_text: str, schema: DatabaseSchema, fallback_sql: str) -> str:
        table = self._preferred_table(schema)
        if not table:
            return fallback_sql

        requested_limit = self.generation_agent._requested_limit(request_text) or self.settings.default_limit
        columns = table.column_names()
        if not columns:
            return f"SELECT * FROM {table.name} LIMIT {requested_limit};"
        select_list = ", ".join(columns[: min(5, len(columns))])
        return f"SELECT {select_list} FROM {table.name} LIMIT {requested_limit};"

    def _preferred_table(self, schema: DatabaseSchema):
        preferred_name = self.preference_service.get("recent_imported_table") if self.preference_service else ""
        if preferred_name:
            table = schema.get_table(preferred_name)
            if table:
                return table

        imported_tables = [table for table in schema.tables.values() if table.name.startswith("imported_")]
        if imported_tables:
            return imported_tables[-1]

        return schema.find_table_for_request("show top rows")


def create_app(schema: Optional[DatabaseSchema] = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
    except ImportError as exc:
        raise RuntimeError("Install fastapi to run the HTTP API.") from exc

    settings = get_settings()
    handlers = ApiHandlers(schema=schema, use_llm=not settings.public_demo)
    app = FastAPI(title="AI SQL Copilot")
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def cleanup_previous_session():
        handlers.cleanup_session()

    @app.on_event("shutdown")
    def cleanup_current_session():
        handlers.cleanup_session()

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "public_demo": settings.public_demo}

    @app.post("/api/connections")
    def create_connection(request: ConnectionCreateRequest):
        return _handle_http(lambda: handlers.create_connection(request), HTTPException)

    @app.get("/api/connections")
    def list_connections():
        return handlers.list_connections()

    @app.post("/api/connections/{connection_id}/test")
    def test_connection(connection_id: str):
        return _handle_http(lambda: handlers.test_connection(connection_id), HTTPException)

    @app.post("/api/schema/refresh")
    def refresh_schema(request: SchemaRefreshRequest):
        return _handle_http(lambda: handlers.refresh_schema(request), HTTPException)

    @app.get("/api/schema")
    def get_schema(connection_id: str):
        return _handle_http(lambda: handlers.get_schema(connection_id), HTTPException)

    @app.post("/api/infer-join")
    def infer_join(request: InferJoinRequest):
        return _handle_http(lambda: handlers.infer_join(request), HTTPException)

    @app.post("/api/datasets/import-csv")
    def import_dataset(request: ImportDatasetRequest):
        return _handle_http(lambda: handlers.import_dataset(request), HTTPException)

    @app.post("/api/ask")
    def ask_database(request: AskDatabaseRequest):
        return _handle_http(lambda: handlers.ask_database(request), HTTPException)

    @app.post("/api/generate-sql")
    def generate_sql(request: GenerateSqlRequest):
        return _handle_http(lambda: handlers.generate_sql(request), HTTPException)

    @app.post("/api/explain-sql")
    def explain_sql(request: ExplainSqlRequest):
        return _handle_http(lambda: handlers.explain_sql(request), HTTPException)

    @app.post("/api/optimize-sql")
    def optimize_sql(request: OptimizeSqlRequest):
        return _handle_http(lambda: handlers.optimize_sql(request), HTTPException)

    @app.post("/api/check-safety")
    def check_safety(request: CheckSafetyRequest):
        return _handle_http(lambda: handlers.check_safety(request), HTTPException)

    @app.post("/api/execute-query")
    def execute_query(request: ExecuteQueryRequest):
        return _handle_http(lambda: handlers.execute_query(request), HTTPException)

    @app.get("/api/query-history")
    def query_history():
        return handlers.query_history()

    @app.get("/api/stream/database-events")
    def stream_database_events(connection_id: str):
        return StreamingResponse(
            handlers.realtime_service.stream_database_events(connection_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app


def _to_dict(value):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _handle_http(callback, http_exception_cls):
    try:
        return callback()
    except PermissionError as exc:
        raise http_exception_cls(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise http_exception_cls(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise http_exception_cls(status_code=503, detail=str(exc))
