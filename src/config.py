import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_database_url: str = "sqlite:///./ai_sql_copilot.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    default_limit: int = 100
    statement_timeout_ms: int = 15000
    read_only_execution: bool = True
    public_demo: bool = False
    use_local_llm: bool = True


def get_settings() -> Settings:
    return Settings(
        app_database_url=os.getenv("APP_DATABASE_URL", "sqlite:///./ai_sql_copilot.db"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),
        default_limit=int(os.getenv("DEFAULT_SQL_LIMIT", "100")),
        statement_timeout_ms=int(os.getenv("STATEMENT_TIMEOUT_MS", "15000")),
        read_only_execution=os.getenv("READ_ONLY_EXECUTION", "true").lower() != "false",
        public_demo=os.getenv("PUBLIC_DEMO", "false").lower() == "true",
        use_local_llm=os.getenv("USE_LOCAL_LLM", "true").lower() != "false",
    )
