import {
  ConnectionProfile,
  DatabaseSchema,
  ExecuteQueryResponse,
  AskDatabaseResponse,
  GenerateSqlResponse,
  ImportDatasetResponse,
  QueryHistoryEntry,
  SafetyResult
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      const payload = JSON.parse(text);
      detail = payload.detail || "";
    } catch {
      detail = text;
    }
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listConnections() {
  return request<ConnectionProfile[]>("/api/connections");
}

export function createConnection(input: {
  name: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password_env_var?: string;
}) {
  return request<ConnectionProfile>("/api/connections", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function getSchema(connectionId: string) {
  return request<DatabaseSchema>(`/api/schema?connection_id=${encodeURIComponent(connectionId)}`);
}

export function refreshSchema(connectionId: string) {
  return request<DatabaseSchema>("/api/schema/refresh", {
    method: "POST",
    body: JSON.stringify({ connection_id: connectionId })
  });
}

export function generateSql(connectionId: string, naturalLanguageRequest: string) {
  return request<GenerateSqlResponse>("/api/generate-sql", {
    method: "POST",
    body: JSON.stringify({
      connection_id: connectionId,
      natural_language_request: naturalLanguageRequest
    })
  });
}

export function checkSafety(connectionId: string, sql: string) {
  return request<SafetyResult>("/api/check-safety", {
    method: "POST",
    body: JSON.stringify({ connection_id: connectionId, sql })
  });
}

export function executeQuery(connectionId: string, sql: string, userRequest: string) {
  return request<ExecuteQueryResponse>("/api/execute-query", {
    method: "POST",
    body: JSON.stringify({
      connection_id: connectionId,
      sql,
      user_request: userRequest,
      confirmed: false
    })
  });
}

export function listHistory() {
  return request<QueryHistoryEntry[]>("/api/query-history");
}

export function importDataset(input: {
  connection_id: string;
  csv_text?: string;
  source_url?: string;
  file_name?: string;
  table_name?: string;
  replace?: boolean;
}) {
  return request<ImportDatasetResponse>("/api/datasets/import-csv", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function askDatabase(connectionId: string, naturalLanguageRequest: string) {
  return request<AskDatabaseResponse>("/api/ask", {
    method: "POST",
    body: JSON.stringify({
      connection_id: connectionId,
      natural_language_request: naturalLanguageRequest
    })
  });
}

export function databaseEventsUrl(connectionId: string) {
  return `${API_BASE}/api/stream/database-events?connection_id=${encodeURIComponent(connectionId)}`;
}
