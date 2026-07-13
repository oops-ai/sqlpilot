# AGENTS.md

## Project: AI SQL Copilot

You are building an AI SQL Copilot, similar to GitHub Copilot but for databases.

The product helps users write, explain, optimize, validate, and safely execute SQL queries using natural language and database schema context.

## Product Goal

Build a developer-focused database assistant that can:

- Convert natural language into SQL
- Explain SQL queries in simple language
- Optimize slow or inefficient SQL
- Detect SQL anti-patterns
- Generate joins automatically using schema metadata
- Run safety checks before execution
- Summarize and visualize query results after execution
- Save query history and learn user preferences over time

## Core Features

### 1. Natural Language to SQL

Convert user requests into SQL queries.

Example user request:

```text
Show total sales by month for 2024
```

Example output:

```sql
SELECT
    DATE_TRUNC('month', order_date) AS month,
    SUM(total_amount) AS total_sales
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date < '2025-01-01'
GROUP BY month
ORDER BY month;
```

Rules:

- Use the connected database schema whenever available.
- Never invent table names or column names when schema context exists.
- Prefer readable SQL over overly clever SQL.
- Add `LIMIT` for exploratory queries unless the user asks for the full dataset.
- Avoid destructive SQL unless the user explicitly requests it.

---

### 2. Explain SQL

Explain what a SQL query does in beginner-friendly language.

The explanation should include:

- Tables used
- Columns selected
- Filters applied
- Joins used
- Aggregations
- Sorting
- Limits
- Possible performance concerns

Example explanation style:

```text
This query reads from the orders table, groups orders by month, and calculates the total sales for each month in 2024. It sorts the result from January to December.
```

---

### 3. Optimize SQL

Suggest better versions of slow or inefficient queries.

Look for:

- Missing indexes
- `SELECT *` on large tables
- Inefficient joins
- Repeated subqueries
- Non-sargable `WHERE` clauses
- Functions applied to indexed columns
- Expensive `ORDER BY` or `GROUP BY`
- Unnecessary nested queries
- Filtering after joining instead of before joining

Optimization output should include:

1. Issues found
2. Why they matter
3. Optimized SQL
4. Index suggestions
5. Expected improvement

---

### 4. Detect SQL Anti-Patterns

Detect risky, inefficient, or unsafe SQL patterns.

Examples:

- `SELECT *` on large tables
- Missing `WHERE` clause on `UPDATE` or `DELETE`
- Cartesian joins
- `LIKE '%keyword%'` on large text columns
- Functions on indexed columns in `WHERE` clauses
- Missing `LIMIT` on exploratory queries
- Too many nested subqueries
- Joining tables without clear join conditions
- Running aggregations on huge tables without filters

---

### 5. Generate Joins Automatically

Infer joins using database schema metadata.

Use:

- Foreign keys
- Primary keys
- Matching column names
- Common naming patterns such as:
  - `user_id`
  - `customer_id`
  - `order_id`
  - `product_id`
  - `account_id`

Rules:

- Prefer explicit foreign key relationships.
- If multiple join paths exist, explain the chosen path.
- If join inference is uncertain, ask for confirmation or show options.

## Agents

### SQL Generation Agent

Responsibilities:

- Convert natural language into SQL.
- Use schema context before writing queries.
- Ask clarifying questions only when needed.
- Generate safe, readable SQL.
- Prefer explicit columns over `SELECT *`.
- Add `LIMIT` for exploratory queries.

Rules:

- Never hallucinate table or column names.
- If schema is missing, request schema or generate a clearly labeled generic example.
- Do not generate destructive queries unless explicitly requested.
- For user-facing SQL, format code cleanly.

Expected output format:

```md
### SQL Query

```sql
...
```

### Explanation

...

### Safety Notes

...
```

---

### SQL Explanation Agent

Responsibilities:

- Explain SQL clearly.
- Break down complex queries step by step.
- Mention performance risks.
- Mention what the result represents.
- Explain joins and aggregations in plain language.

Tone:

- Simple
- Practical
- Beginner-friendly
- No unnecessary theory

Expected output format:

```md
### What This Query Does

...

### Tables Used

...

### Filters

...

### Joins

...

### Performance Notes

...
```

---

### SQL Optimization Agent

Responsibilities:

- Analyze query performance.
- Suggest rewritten SQL.
- Recommend indexes.
- Explain why the optimized query is better.

Look for:

- Full table scans
- Missing indexes
- Inefficient joins
- Repeated logic
- Unnecessary columns
- Expensive sorting
- Poor filtering order

Expected output format:

```md
### Issues Found

...

### Optimized Query

```sql
...
```

### Why This Is Better

...

### Index Suggestions

...
```

---

### SQL Safety Agent

Responsibilities:

- Run before query execution.
- Detect risky queries.
- Estimate possible impact.
- Warn the user before dangerous execution.
- Block destructive queries unless the user confirms.

Check for:

- `DELETE` without `WHERE`
- `UPDATE` without `WHERE`
- `DROP`
- `TRUNCATE`
- `ALTER`
- Full table scans
- Queries that may return millions of rows
- Missing `LIMIT`
- Cross joins
- High-cost joins

Expected JSON response:

```json
{
  "safe": false,
  "risk_level": "high",
  "warnings": [],
  "suggested_fix": ""
}
```

Risk levels:

- `safe`
- `low`
- `medium`
- `high`
- `dangerous`

Rules:

- Do not execute dangerous queries automatically.
- Require explicit confirmation for destructive queries.
- Suggest safer alternatives when possible.

---

### Query Result Agent

Responsibilities:

- Run after query execution.
- Summarize query results.
- Suggest useful visualizations.
- Detect unusual patterns.
- Save query history.
- Learn user preferences.

Examples:

- If result has a date/time column and numeric column, suggest a line chart.
- If result has a category column and count/sum column, suggest a bar chart.
- If result is small, show a table.
- If result is empty, suggest debugging steps.
- If result has geographic fields, suggest a map when appropriate.

Expected JSON response:

```json
{
  "summary": "",
  "row_count": 0,
  "visualization_suggestion": "",
  "follow_up_questions": [],
  "learned_preferences": []
}
```

## Hooks

### Before Execution Hook

This hook must run before any SQL query is executed.

Responsibilities:

1. Validate SQL syntax.
2. Estimate query cost.
3. Detect dangerous operations.
4. Warn if query may return too many rows.
5. Suggest adding `LIMIT` if needed.
6. Block destructive queries unless the user confirms.

Expected output:

```json
{
  "query": "",
  "estimated_cost": "low | medium | high",
  "risk_level": "safe | warning | dangerous",
  "warnings": [],
  "requires_confirmation": false
}
```

Implementation notes:

- Use `EXPLAIN` for cost estimation where possible.
- Do not use `EXPLAIN ANALYZE` before user confirmation because it may execute the query.
- For PostgreSQL, inspect the query plan for sequential scans, nested loops, estimated rows, and cost.
- If estimated rows are very high, warn the user.

---

### After Execution Hook

This hook must run after a SQL query executes successfully.

Responsibilities:

1. Summarize the result.
2. Suggest charts or visualizations.
3. Save query and metadata to history.
4. Store user preferences.
5. Suggest useful follow-up questions.

Expected output:

```json
{
  "summary": "",
  "row_count": 0,
  "visualization_suggestion": "",
  "follow_up_questions": [],
  "learned_preferences": []
}
```

Query metadata to save:

- Original user request
- Generated SQL
- Execution time
- Row count
- Database name
- Tables used
- Timestamp
- Safety result
- Visualization used

## Suggested Backend Structure

```txt
src/
  agents/
    sql_generation_agent.py
    sql_explanation_agent.py
    sql_optimization_agent.py
    sql_safety_agent.py
    result_agent.py

  hooks/
    before_execution.py
    after_execution.py

  database/
    connection.py
    schema_loader.py
    query_executor.py
    cost_estimator.py

  services/
    llm_service.py
    query_history_service.py
    preference_service.py
    visualization_service.py

  api/
    routes.py
    schemas.py

  tests/
    test_sql_generation.py
    test_sql_explanation.py
    test_sql_safety.py
    test_query_optimizer.py
    test_hooks.py
```

## Suggested Frontend Structure

```txt
frontend/
  app/
    page.tsx
    layout.tsx

  components/
    ChatPanel.tsx
    SqlEditor.tsx
    QueryResultTable.tsx
    QueryHistory.tsx
    SafetyWarning.tsx
    VisualizationPanel.tsx

  lib/
    api.ts
    types.ts
```

## Recommended Tech Stack

Backend:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- OpenAI API or local LLM provider
- `sqlparse` or `sqlglot` for SQL parsing
- PostgreSQL `EXPLAIN` for query cost estimation
- `pg_stat_statements` for performance monitoring

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS
- Monaco Editor for SQL editing
- Recharts or Chart.js for visualizations

Database:

- PostgreSQL for main app storage
- User-connected PostgreSQL database for query execution

## API Endpoints

Suggested FastAPI endpoints:

```txt
POST /api/generate-sql
POST /api/explain-sql
POST /api/optimize-sql
POST /api/check-safety
POST /api/execute-query
GET  /api/query-history
GET  /api/schema
POST /api/preferences
```

### POST /api/generate-sql

Input:

```json
{
  "natural_language_request": "Show total revenue by month",
  "database_id": "default"
}
```

Output:

```json
{
  "sql": "SELECT ...",
  "explanation": "...",
  "safety_notes": []
}
```

---

### POST /api/check-safety

Input:

```json
{
  "sql": "SELECT * FROM orders"
}
```

Output:

```json
{
  "safe": true,
  "risk_level": "medium",
  "warnings": ["Query has no LIMIT and may return many rows."],
  "requires_confirmation": false
}
```

---

### POST /api/execute-query

Input:

```json
{
  "sql": "SELECT ...",
  "confirmed": false
}
```

Output:

```json
{
  "columns": [],
  "rows": [],
  "row_count": 0,
  "execution_time_ms": 0,
  "summary": "",
  "visualization_suggestion": ""
}
```

## Safety Rules

Never execute dangerous queries without confirmation.

Dangerous SQL includes:

```sql
DROP TABLE
TRUNCATE TABLE
DELETE FROM table_name
UPDATE table_name SET column = value
ALTER TABLE
```

Always warn users before:

- Large scans
- Missing `WHERE` clauses
- Missing `LIMIT`
- High-cost joins
- Queries affecting many rows
- Queries that expose sensitive columns

Sensitive columns may include:

- email
- phone
- address
- ssn
- password
- token
- api_key
- credit_card
- salary
- date_of_birth

## Query Cost Estimation Guidelines

For PostgreSQL:

Use:

```sql
EXPLAIN (FORMAT JSON) <query>;
```

Inspect:

- Total cost
- Estimated rows
- Sequential scans
- Join types
- Sort operations
- Aggregate operations

Cost levels:

- Low: small result set, indexed filters, limited rows
- Medium: moderate scan or aggregation
- High: full table scans, large joins, large aggregations
- Dangerous: destructive query or query likely to affect large data

## Query History

Save every generated and executed query.

Suggested schema:

```sql
CREATE TABLE query_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_request TEXT,
    generated_sql TEXT NOT NULL,
    executed BOOLEAN DEFAULT FALSE,
    execution_time_ms INTEGER,
    row_count INTEGER,
    database_name TEXT,
    tables_used TEXT[],
    safety_level TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## User Preferences

Learn user preferences from usage.

Examples:

- Preferred SQL dialect
- Preferred chart type
- Usually wants `LIMIT 100`
- Prefers CTEs over nested subqueries
- Prefers lowercase or uppercase SQL keywords
- Frequently used tables

Suggested schema:

```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## SQL Style Guide

Generated SQL should:

- Use clear indentation
- Use explicit column names
- Use meaningful aliases
- Prefer CTEs for complex queries
- Avoid unnecessary nested subqueries
- Include comments only when helpful
- Use `LIMIT` for exploratory queries

Preferred style:

```sql
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', order_date) AS month,
        SUM(total_amount) AS total_sales
    FROM orders
    WHERE order_date >= '2024-01-01'
      AND order_date < '2025-01-01'
    GROUP BY DATE_TRUNC('month', order_date)
)
SELECT
    month,
    total_sales
FROM monthly_sales
ORDER BY month;
```

## MVP Goals

Build these first:

1. User enters a natural language question.
2. App generates SQL using schema context.
3. User can explain generated SQL.
4. Before execution hook checks safety.
5. Query executes only if safe.
6. Results are shown in a table.
7. After execution hook summarizes results.
8. Query history is saved.

## MVP User Flow

1. User connects a PostgreSQL database.
2. App loads database schema.
3. User asks a question in natural language.
4. SQL Generation Agent creates SQL.
5. SQL Safety Agent checks risk.
6. User reviews SQL.
7. Query executes if safe.
8. Result appears in table.
9. Result Agent suggests visualization.
10. Query is saved in history.

## Future Improvements

- Multi-database support
- MySQL support
- SQLite support
- Snowflake support
- BigQuery support
- User-specific query style learning
- Automatic dashboard generation
- Schema-aware autocomplete
- Query performance monitoring
- Team-shared query history
- Role-based query permissions
- Sensitive data detection
- Query versioning
- Slack or Teams integration
- MCP server for database tools
- VS Code extension
- Browser-based SQL workbench

## Codex Instruction

When working on this project, follow this file as the source of truth.

Prioritize building a working MVP before adding advanced features.

Do not skip safety checks.

Do not execute destructive SQL without explicit confirmation.

Start with PostgreSQL support only.

Use clean modular code and write tests for all agents and hooks.
