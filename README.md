# SQLPilot

SQLPilot is a chat-first data assistant for PostgreSQL. Users describe what they want in plain language, and the app turns that into safe data actions, returns the result in chat, and keeps SQL available only when needed.

## Current State

Implemented today:

- Chat-first natural language workflow
- Result-first answers with optional SQL visibility
- PostgreSQL connection management
- CSV import into a real table in the connected database
- URL-based CSV import
- Schema introspection
- SQL generation with schema context
- SQL explanation and optimization helpers
- Read-only safety checks before execution
- Query execution and result summaries
- Query history and preference storage
- MCP server for SQL and database tool access
- Session cleanup for imported datasets on backend shutdown
- Auto-launch dev stack with browser open on macOS

Not implemented yet:

- ZIP archive import and extraction
- Multi-database support beyond PostgreSQL
- Write actions without explicit confirmation

## How It Works

1. The user connects a PostgreSQL database.
2. The app loads the schema.
3. The user imports CSV data or asks a question about connected data.
4. SQLPilot decides the right read-only action.
5. Safety checks run before execution.
6. The backend executes the query.
7. The answer returns in chat, with SQL hidden unless requested.

Imported CSV data is stored as a real table in PostgreSQL. The app also stores metadata such as connections, schema snapshots, query history, and preferences in the local app database `ai_sql_copilot.db`.

Imported dataset tables are treated as session data and are deleted when the backend session ends normally.

## Tech Stack

- Backend: Python, FastAPI, PostgreSQL, SQLAlchemy, Pydantic, sqlglot
- LLM: local Ollama
- Frontend: Next.js, React, TypeScript
- UI helpers: Monaco Editor, Recharts
- MCP: stdio server exposing SQL and database tools

## Local Setup

Install backend dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Configure environment:

```sh
cp .env.example .env
```

Start Ollama and pull the configured model:

```sh
/Applications/Ollama.app/Contents/Resources/ollama pull qwen2.5-coder:1.5b
```

Run the full local stack:

```sh
cd frontend
npm run dev
```

That starts:

- Backend at `http://127.0.0.1:8000`
- Frontend at `http://127.0.0.1:3000`
- MCP server in the same launcher session

On macOS, the launcher opens the frontend in your default browser automatically.

If you only want the API:

```sh
sh scripts/start_backend.sh
```

If you only want the UI:

```sh
cd frontend
npm run dev:ui
```

If you only want the MCP server:

```sh
sh scripts/start_mcp_server.sh
```

## Testing

Run the backend test suite:

```sh
python3 -m unittest discover -s tests
```

The current suite covers SQL generation, safety, dataset import, persistence, hooks, and API handler behavior.

## Environment Variables

Key settings from `.env`:

- `APP_DATABASE_URL` for app metadata storage
- `OLLAMA_BASE_URL` for local model access
- `OLLAMA_MODEL` for the Ollama model name
- `DEFAULT_SQL_LIMIT` for exploratory query defaults
- `STATEMENT_TIMEOUT_MS` for query timeout
- `READ_ONLY_EXECUTION` to keep execution read-only by default
- `PUBLIC_DEMO` to disable the local model path for hosted demo use
- `USE_LOCAL_LLM` to toggle Ollama-backed generation
- `CORS_ORIGINS` for frontend/backend access

## MCP

The MCP server is a tool bridge, not the model itself. It exposes actions such as:

- list connections
- read and refresh schema
- generate SQL
- explain SQL
- optimize SQL
- check safety
- inspect query history
- execute SQL against the target database or app metadata database

## Notes

- Read-only actions run by default.
- Destructive or mutating actions require explicit confirmation.
- SQLPilot should answer in chat first, not force users to work in SQL unless they ask for it.
