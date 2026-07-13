export type ConnectionProfile = {
  id: string;
  name: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password_env_var?: string;
};

export type ColumnInfo = {
  name: string;
  data_type: string;
  sensitive: boolean;
  nullable: boolean;
};

export type TableInfo = {
  name: string;
  columns: ColumnInfo[];
  primary_key?: string;
};

export type DatabaseSchema = {
  tables: Record<string, TableInfo>;
};

export type SafetyResult = {
  safe: boolean;
  risk_level: string;
  warnings: string[];
  suggested_fix: string;
  requires_confirmation: boolean;
};

export type GenerateSqlResponse = {
  sql: string;
  explanation: string;
  safety_notes: string[];
};

export type ImportDatasetResponse = {
  connection_id: string;
  table_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  source_type: string;
  imported_schema: DatabaseSchema;
};

export type AskDatabaseResponse = {
  sql: string;
  explanation: string;
  safety: SafetyResult;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  summary: string;
  visualization_suggestion: string;
};

export type ExecuteQueryResponse = {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  summary: string;
  visualization_suggestion: string;
};

export type QueryHistoryEntry = {
  id: string;
  user_request?: string;
  generated_sql: string;
  executed: boolean;
  row_count?: number;
  safety_level: string;
  created_at: string;
};

export type DatabaseEvent = {
  table?: string;
  operation?: string;
  record?: Record<string, unknown>;
  changed_at?: string;
  channel?: string;
  message?: string;
  eventType: string;
};
