"use client";

import { useState } from "react";
import { ConnectionProfile } from "../lib/types";

export function ConnectionPanel({
  connections,
  connectionId,
  onConnectionChange,
  onCreate,
  onRefreshSchema,
  busy,
  busyAction
}: {
  connections: ConnectionProfile[];
  connectionId: string;
  onConnectionChange: (id: string) => void;
  onCreate: (input: {
    name: string;
    host: string;
    port: number;
    database_name: string;
    username: string;
    password_env_var?: string;
  }) => Promise<void>;
  onRefreshSchema: () => void;
  busy: boolean;
  busyAction: string;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState(5432);
  const [databaseName, setDatabaseName] = useState("");
  const [username, setUsername] = useState("");
  const [passwordEnvVar, setPasswordEnvVar] = useState("");

  async function submit() {
    await onCreate({
      name,
      host,
      port,
      database_name: databaseName,
      username,
      password_env_var: passwordEnvVar
    });
    setName("");
    setDatabaseName("");
    setUsername("");
    setPasswordEnvVar("");
    setOpen(false);
  }

  return (
    <section className="stack">
      <div>
        <h2 className="section-title">Connection</h2>
        <p className="muted">Pick the seeded Olist demo or add another Postgres target.</p>
      </div>
      <select value={connectionId} onChange={(event) => onConnectionChange(event.target.value)}>
        <option value="">No connection</option>
        {connections.map((connection) => (
          <option key={connection.id} value={connection.id}>
            {connection.name}
          </option>
        ))}
      </select>
      <div className="toolbar">
        <button onClick={() => setOpen((next) => !next)}>{open ? "Close" : "New"}</button>
        <button onClick={onRefreshSchema} disabled={!connectionId || busy}>
          {busyAction === "schema" ? "Refreshing..." : "Refresh Schema"}
        </button>
      </div>
      {open ? (
        <div className="connection-form stack">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Connection name" />
          <input value={host} onChange={(event) => setHost(event.target.value)} placeholder="Host" />
          <input
            value={port}
            type="number"
            onChange={(event) => setPort(Number(event.target.value))}
            placeholder="Port"
          />
          <input
            value={databaseName}
            onChange={(event) => setDatabaseName(event.target.value)}
            placeholder="Database"
          />
          <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" />
          <input
            value={passwordEnvVar}
            onChange={(event) => setPasswordEnvVar(event.target.value)}
            placeholder="Password env var"
          />
          <button
            className="primary"
            onClick={submit}
            disabled={busy || !name || !host || !databaseName || !username}
          >
            {busyAction === "connection" ? "Saving..." : "Save Connection"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
