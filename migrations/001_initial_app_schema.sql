CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS database_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    database_type TEXT NOT NULL DEFAULT 'postgresql',
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    database_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password_env_var TEXT,
    read_only BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, name)
);

CREATE TABLE IF NOT EXISTS schema_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES database_connections(id) ON DELETE CASCADE,
    schema_json JSONB NOT NULL,
    table_count INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER NOT NULL DEFAULT 0,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES database_connections(id) ON DELETE SET NULL,
    user_request TEXT,
    generated_sql TEXT NOT NULL,
    executed BOOLEAN NOT NULL DEFAULT FALSE,
    safety_level TEXT NOT NULL,
    safety_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_time_ms INTEGER,
    row_count INTEGER,
    tables_used TEXT[] NOT NULL DEFAULT '{}',
    visualization_suggestion TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, preference_key)
);

CREATE TABLE IF NOT EXISTS saved_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES database_connections(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    sql TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, name)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    actor TEXT,
    entity_type TEXT,
    entity_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_database_connections_workspace_id
    ON database_connections(workspace_id);

CREATE INDEX IF NOT EXISTS idx_schema_snapshots_connection_id_refreshed_at
    ON schema_snapshots(connection_id, refreshed_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_history_workspace_created_at
    ON query_history(workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_history_connection_created_at
    ON query_history(connection_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_preferences_workspace_id
    ON user_preferences(workspace_id);

CREATE INDEX IF NOT EXISTS idx_saved_queries_workspace_id
    ON saved_queries(workspace_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_workspace_created_at
    ON audit_events(workspace_id, created_at DESC);

INSERT INTO workspaces (name)
VALUES ('Personal')
ON CONFLICT (name) DO NOTHING;
