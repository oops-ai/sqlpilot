"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { ConnectionPanel } from "../components/ConnectionPanel";
import { ImportPanel } from "../components/ImportPanel";
import { QueryHistory } from "../components/QueryHistory";
import { QueryResultTable } from "../components/QueryResultTable";
import { SafetyWarning } from "../components/SafetyWarning";
import { SchemaBrowser } from "../components/SchemaBrowser";
import { SqlEditor } from "../components/SqlEditor";
import { VisualizationPanel } from "../components/VisualizationPanel";
import { LiveActivityPanel } from "../components/LiveActivityPanel";
import {
  askDatabase,
  checkSafety,
  createConnection,
  executeQuery,
  importDataset,
  getSchema,
  listConnections,
  listHistory,
  refreshSchema
} from "../lib/api";
import { ConnectionProfile, DatabaseSchema, ExecuteQueryResponse, QueryHistoryEntry, SafetyResult } from "../lib/types";
import { AskDatabaseResponse } from "../lib/types";

export default function HomePage() {
  const [connections, setConnections] = useState<ConnectionProfile[]>([]);
  const [connectionId, setConnectionId] = useState("");
  const [schema, setSchema] = useState<DatabaseSchema | null>(null);
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [prompt, setPrompt] = useState("");
  const [sql, setSql] = useState("");
  const [explanation, setExplanation] = useState("");
  const [showSql, setShowSql] = useState(false);
  const [transcript, setTranscript] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [safety, setSafety] = useState<SafetyResult | null>(null);
  const [checkedSql, setCheckedSql] = useState("");
  const [result, setResult] = useState<ExecuteQueryResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyAction, setBusyAction] = useState<"" | "generate" | "ask" | "safety" | "execute" | "schema" | "connection" | "import">("");

  const selectedConnection = useMemo(
    () => connections.find((connection) => connection.id === connectionId),
    [connections, connectionId]
  );
  const isBusy = busyAction !== "";
  const safetyIsCurrent = Boolean(safety && checkedSql === sql);
  const canExecute = Boolean(connectionId && sql.trim() && safetyIsCurrent && safety?.safe && !isBusy);
  const schemaTableCount = schema ? Object.keys(schema.tables).length : 0;
  const recentQuery = history[0];

  useEffect(() => {
    listConnections()
      .then((items) => {
        setConnections(items);
        setConnectionId(items[0]?.id ?? "");
      })
      .catch((err) => setError(err.message));
    listHistory().then(setHistory).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!connectionId) {
      setSchema(null);
      return;
    }
    getSchema(connectionId).then(setSchema).catch(() => setSchema(null));
  }, [connectionId]);

  async function runSafety() {
    setBusyAction("safety");
    setError("");
    setNotice("");
    try {
      const checked = await checkSafety(connectionId, sql);
      setSafety(checked);
      setCheckedSql(sql);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check safety");
    } finally {
      setBusyAction("");
    }
  }

  async function runExecute() {
    setBusyAction("execute");
    setError("");
    setNotice("");
    try {
      const checked = safetyIsCurrent && safety ? safety : await checkSafety(connectionId, sql);
      setSafety(checked);
      setCheckedSql(sql);
      if (!checked.safe) {
        setError("Execution blocked by safety checks.");
        return;
      }
      setResult(await executeQuery(connectionId, sql, prompt));
      setHistory(await listHistory());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute query");
    } finally {
      setBusyAction("");
    }
  }

  async function runCreateConnection(input: {
    name: string;
    host: string;
    port: number;
    database_name: string;
    username: string;
    password_env_var?: string;
  }) {
    setBusyAction("connection");
    setError("");
    setNotice("");
    try {
      const created = await createConnection(input);
      const nextConnections = await listConnections();
      setConnections(nextConnections);
      setConnectionId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create connection");
    } finally {
      setBusyAction("");
    }
  }

  async function runRefreshSchema() {
    if (!connectionId) return;
    setBusyAction("schema");
    setError("");
    setNotice("");
    try {
      setSchema(await refreshSchema(connectionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh schema");
    } finally {
      setBusyAction("");
    }
  }

  async function runImportDataset(input: {
    connection_id: string;
    csv_text?: string;
    source_url?: string;
    file_name?: string;
    table_name?: string;
    replace?: boolean;
  }) {
    setBusyAction("import");
    setError("");
    setNotice("");
    try {
      const imported = await importDataset(input);
      setSchema(imported.imported_schema);
      setNotice(`Imported ${imported.row_count} rows into ${imported.table_name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import CSV");
    } finally {
      setBusyAction("");
    }
  }

  function updateSql(nextSql: string) {
    setSql(nextSql);
    setSafety(null);
    setCheckedSql("");
    setResult(null);
  }

  async function runAsk() {
    setBusyAction("ask");
    setError("");
    setNotice("");
    try {
      const response = await askDatabase(connectionId, prompt);
      setTranscript((messages) => [
        ...messages,
        { role: "user", content: prompt },
        { role: "assistant", content: formatAssistantMessage(response) }
      ]);
      setSql(response.sql);
      setExplanation(response.explanation);
      setShowSql(false);
      setSafety(response.safety);
      setCheckedSql(response.sql);
      setResult({
        columns: response.columns,
        rows: response.rows,
        row_count: response.row_count,
        execution_time_ms: response.execution_time_ms,
        summary: response.summary,
        visualization_suggestion: response.visualization_suggestion
      });
      setHistory(await listHistory());
      setPrompt("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ask database");
    } finally {
      setBusyAction("");
    }
  }

  async function copySql() {
    if (!sql.trim()) return;
    try {
      await navigator.clipboard.writeText(sql);
      setNotice("SQL copied.");
      setError("");
    } catch {
      setError("Could not copy SQL.");
    }
  }

  function formatSql() {
    if (!sql.trim()) return;
    updateSql(formatSqlText(sql));
    setNotice("SQL formatted.");
    setError("");
  }

  return (
    <main className="workbench">
      <header className="topbar">
        <div className="brand-lockup">
          <p className="eyebrow">AI SQL Copilot</p>
          <h1>Command Center</h1>
          <p className="topbar-copy">Ask questions and get answers from connected data in one workspace.</p>
        </div>
        <div className="topbar-status">
          <span className={connectionId ? "pill good" : "pill"}>{selectedConnection?.name ?? "No connection"}</span>
          <span className="pill">Ollama local</span>
          {isBusy ? <span className="pill active">{busyLabel(busyAction)}</span> : null}
        </div>
      </header>

      <div className="app-shell">
        <aside className="sidebar stack">
          <ConnectionPanel
            connections={connections}
            connectionId={connectionId}
            onConnectionChange={setConnectionId}
            onCreate={runCreateConnection}
            onRefreshSchema={runRefreshSchema}
            busy={isBusy}
            busyAction={busyAction}
          />
          <ImportPanel connectionId={connectionId} onImport={runImportDataset} busy={isBusy} busyAction={busyAction} />
          <div className="sidebar-card">
            <p className="section-title">Workspace</p>
            <div className="sidebar-metric">
              <strong>{selectedConnection ? selectedConnection.database_name : "No database selected"}</strong>
              <span className="muted">{schemaTableCount} tables loaded</span>
            </div>
            <div className="sidebar-metric">
              <strong>{history.length} queries</strong>
              <span className="muted">Saved in history</span>
            </div>
          </div>
          <SchemaBrowser schema={schema} />
          <QueryHistory history={history} onSelect={updateSql} />
        </aside>

        <section className="main-panel">
          <section className="summary-grid">
            <div className="stat-card accent">
              <span className="stat-label">Connection</span>
              <strong>{selectedConnection?.name ?? "None"}</strong>
              <span>{selectedConnection ? `${selectedConnection.host}:${selectedConnection.port}` : "Choose a database"}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Schema</span>
              <strong>{schemaTableCount}</strong>
              <span>Tables available for generation</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Latest answer</span>
              <strong>{recentQuery?.safety_level ?? "—"}</strong>
              <span>{recentQuery?.user_request ?? "No recent answer"}</span>
            </div>
          </section>

          <ChatPanel
            prompt={prompt}
            onPromptChange={setPrompt}
            onAsk={runAsk}
            disabled={!connectionId || isBusy}
            asking={busyAction === "ask"}
            transcript={transcript}
          />
          <div className="toolbar">
            <button type="button" onClick={() => setShowSql((next) => !next)} disabled={!sql.trim()}>
              {showSql ? "Hide SQL" : "Show SQL"}
            </button>
          </div>
          {showSql ? (
            <>
              <div className="editor-header">
                <div>
                  <h2>SQL</h2>
                  <p className="muted">{safetyIsCurrent ? "Safety checked for current SQL." : "Check safety after editing."}</p>
                </div>
                <div className="toolbar">
                  <button type="button" onClick={formatSql} disabled={!sql.trim() || isBusy}>
                    Format SQL
                  </button>
                  <button type="button" onClick={copySql} disabled={!sql.trim()}>
                    Copy SQL
                  </button>
                </div>
              </div>
              <SqlEditor value={sql} onChange={updateSql} />
              <div className="action-bar">
                <button onClick={runSafety} disabled={!sql.trim() || isBusy}>
                  {busyAction === "safety" ? "Checking..." : "Check Safety"}
                </button>
                <button className="primary" onClick={runExecute} disabled={!canExecute}>
                  {busyAction === "execute" ? "Executing..." : "Execute Read"}
                </button>
                {!safetyIsCurrent && sql.trim() ? <span className="inline-note">Safety check required before execution.</span> : null}
                {notice ? <span className="inline-note success">{notice}</span> : null}
                {error ? <span className="inline-note danger">{error}</span> : null}
              </div>
            </>
          ) : null}
          <QueryResultTable result={result} />
        </section>

        <aside className="right-panel stack">
          <section>
            <h2 className="section-title">Safety</h2>
            <SafetyWarning safety={safety} />
          </section>
          <VisualizationPanel result={result} />
          <LiveActivityPanel connectionId={connectionId} />
        </aside>
      </div>
    </main>
  );
}

function busyLabel(action: string) {
  switch (action) {
    case "generate":
      return "Generating";
    case "ask":
      return "Answering";
    case "safety":
      return "Checking safety";
    case "execute":
      return "Executing";
    case "schema":
      return "Refreshing schema";
    case "connection":
      return "Saving connection";
    case "import":
      return "Importing data";
    default:
      return "Working";
  }
}

function formatSqlText(value: string) {
  return value
    .replace(/\s+/g, " ")
    .replace(/\bSELECT\b/gi, "SELECT\n    ")
    .replace(/\bFROM\b/gi, "\nFROM")
    .replace(/\bWHERE\b/gi, "\nWHERE")
    .replace(/\bGROUP BY\b/gi, "\nGROUP BY")
    .replace(/\bORDER BY\b/gi, "\nORDER BY")
    .replace(/\bLIMIT\b/gi, "\nLIMIT")
    .replace(/,\s*/g, ",\n    ")
    .replace(/\n\s*\n/g, "\n")
    .trim()
    .replace(/;?$/, ";");
}

function formatAssistantMessage(response: AskDatabaseResponse) {
  const pieces = [
    response.summary,
    `${response.row_count} row${response.row_count === 1 ? "" : "s"} returned.`,
  ];
  if (response.visualization_suggestion) {
    pieces.push(`Suggested view: ${response.visualization_suggestion}.`);
  }
  return pieces.join(" ");
}
