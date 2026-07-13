from typing import Any, Dict, List

try:
    from pydantic import BaseModel
except ImportError:
    from dataclasses import dataclass

    class BaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self, "__annotations__", {})
            for field, default in self.__class__.__dict__.items():
                if field.startswith("_") or callable(default):
                    continue
                if field in annotations:
                    setattr(self, field, kwargs.pop(field, default))
            for field in annotations:
                if field in kwargs:
                    setattr(self, field, kwargs.pop(field))
            if kwargs:
                unknown = ", ".join(kwargs)
                raise TypeError(f"Unknown fields: {unknown}")

        def model_dump(self):
            return dict(self.__dict__)


class ConnectionCreateRequest(BaseModel):
    name: str
    host: str
    database_name: str
    username: str
    port: int = 5432
    password_env_var: str = ""


class GenerateSqlRequest(BaseModel):
    natural_language_request: str
    database_id: str = "default"
    connection_id: str = ""


class GenerateSqlResponse(BaseModel):
    sql: str
    explanation: str
    safety_notes: List[str] = []


class ExplainSqlRequest(BaseModel):
    sql: str


class OptimizeSqlRequest(BaseModel):
    sql: str
    connection_id: str = ""


class CheckSafetyRequest(BaseModel):
    sql: str
    connection_id: str = ""


class SchemaRefreshRequest(BaseModel):
    connection_id: str


class InferJoinRequest(BaseModel):
    connection_id: str
    left_table: str
    right_table: str


class ImportDatasetRequest(BaseModel):
    connection_id: str
    csv_text: str = ""
    source_url: str = ""
    file_name: str = ""
    table_name: str = ""
    replace: bool = False


class ImportDatasetResponse(BaseModel):
    connection_id: str
    table_name: str
    row_count: int
    column_count: int
    columns: List[str]
    source_type: str
    imported_schema: Dict[str, Any]


class AskDatabaseRequest(BaseModel):
    connection_id: str
    natural_language_request: str


class AskDatabaseResponse(BaseModel):
    sql: str
    explanation: str
    safety: Dict[str, Any]
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int
    summary: str
    visualization_suggestion: str


class ExecuteQueryRequest(BaseModel):
    sql: str
    confirmed: bool = False
    connection_id: str = ""
    user_request: str = ""


class ExecuteQueryResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int
    summary: str
    visualization_suggestion: str
