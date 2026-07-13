import json
from dataclasses import dataclass
from typing import Any, Dict

from src.config import Settings, get_settings
from src.database.schema_loader import DatabaseSchema


class LLMService:
    def complete(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class OllamaLLMService(LLMService):
    settings: Settings = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    def complete(self, prompt: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("Install httpx to use Ollama-backed generation.") from exc

        response = httpx.post(
            f"{self.settings.ollama_base_url}/api/generate",
            json={
                "model": self.settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("response", "")


def build_sql_generation_prompt(request: str, schema: DatabaseSchema, default_limit: int) -> str:
    schema_payload = json.dumps(schema.to_dict(), indent=2)
    return f"""
You are an expert PostgreSQL SQL copilot.
Return only JSON with keys: sql, explanation, assumptions, safety_notes.
Use only tables and columns from this schema. Do not invent identifiers.
Generate read-only PostgreSQL SQL only.
Add LIMIT {default_limit} for exploratory row-level SELECT queries unless the user explicitly asks for the full dataset.
For month or time-bucket grouping, use PostgreSQL DATE_TRUNC, not YEAR() or MONTH().

Schema:
{schema_payload}

User request:
{request}
""".strip()


def parse_llm_json_response(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
