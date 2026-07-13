# AI SQL Copilot

Full-stack MVP for a PostgreSQL-first SQL copilot with a local LLM path.

Implemented:

- Schema-aware natural language to SQL scaffold
- SQL explanation
- SQL optimization hints
- Read-only SQL safety checks
- Before/after execution hooks
- Query result summaries and visualization suggestions
- SQLite-backed connection profiles, schema snapshots, query history, and preferences
- PostgreSQL schema introspection and read-only execution
- Ollama-backed local LLM adapter with deterministic fallback
- FastAPI-compatible route handlers
- Next.js SQL workbench frontend

Install backend dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Configure environment:

```sh
cp .env.example .env
```

Start Ollama and make sure the configured model exists:

```sh
/Applications/Ollama.app/Contents/Resources/ollama pull qwen2.5-coder:1.5b
```

Run backend tests:

```sh
python3 -m unittest discover -s tests
```

Run API:

```sh
sh scripts/start_backend.sh
```

Run frontend:

```sh
npm --prefix frontend install
npm --prefix frontend run dev
```

Run the full local stack:

```sh
sh scripts/start_dev_stack.sh
```

That starts:

- backend on `http://127.0.0.1:8000`
- frontend on `http://127.0.0.1:3000`
- MCP server in the same launcher session

If `npm` is missing, the launcher still starts the backend and MCP server, but it cannot start the frontend until Node is installed.
On macOS, the launcher opens the app in your default browser automatically.
Set `OPEN_BROWSER=false` to disable that behavior.

For UI-only frontend development, run:

```sh
npm --prefix frontend run dev:ui
```

Local LLM defaults:

- Ollama URL: `http://localhost:11434`
- Model env var: `OLLAMA_MODEL`, default `qwen2.5-coder:1.5b`
- API base env var for frontend: `NEXT_PUBLIC_API_BASE_URL`

Useful local commands:

```sh
sh scripts/start_ollama.sh
sh scripts/pull_model.sh
sh scripts/start_backend.sh
sh scripts/start_frontend.sh
sh scripts/start_mcp_server.sh
sh scripts/start_dev_stack.sh
```

Connection passwords:

- The app stores the name of an environment variable, not the password itself.
- Set that environment variable before starting the API, then use the same name in the connection form.

Olist dataset import:

```sh
python3 scripts/import_olist_dataset.py --source /path/to/brazilian-ecommerce.zip --dsn postgresql://postgres@127.0.0.1:5432/ai_sql_copilot --replace
```

- `--source` can point to the Kaggle zip file or an extracted folder.
- `--replace` reloads the Olist tables before inserting fresh rows.
- After import, refresh schema in the app and use the `olist_*` tables for queries.

Live demo rows:

```sh
python3 scripts/live_event_writer.py --dsn postgresql://postgres@127.0.0.1:5432/ai_sql_copilot_demo --count 5 --interval-seconds 2
```

Public-demo seeding:

```sh
python3 scripts/seed_public_demo.py --app-dsn postgresql://postgres@127.0.0.1:5432/ai_sql_copilot --name "Olist Demo" --host 127.0.0.1 --database ai_sql_copilot_demo --username postgres
```

Public deployment env vars:

- `APP_DATABASE_URL=postgresql://...` for app metadata
- `PUBLIC_DEMO=true` to disable the local Ollama path
- `USE_LOCAL_LLM=false` for the hosted demo
- `CORS_ORIGINS=https://your-frontend.vercel.app` for the backend
- `NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com`

Render backend:

- Use the included [render.yaml](./render.yaml).
- Point `APP_DATABASE_URL` at the Neon Postgres database you create.
- Set `PUBLIC_DEMO=true` and `USE_LOCAL_LLM=false`.
- Set `CORS_ORIGINS` to your Vercel frontend URL.

Vercel frontend:

- Set the project root to `frontend/`.
- Set `NEXT_PUBLIC_API_BASE_URL` to the Render backend URL.
- Redeploy after the backend URL is fixed.

MCP server:

- Run `sh scripts/start_mcp_server.sh` for a local stdio server.
- It reuses saved Postgres connections and exposes SQL, schema, history, and admin tools.
