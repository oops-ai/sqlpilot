"use client";

import { useMemo, useState } from "react";

type ImportMode = "file" | "url";

export function ImportPanel({
  connectionId,
  onImport,
  busy,
  busyAction
}: {
  connectionId: string;
  onImport: (input: {
    connection_id: string;
    csv_text?: string;
    source_url?: string;
    file_name?: string;
    table_name?: string;
    replace?: boolean;
  }) => Promise<void>;
  busy: boolean;
  busyAction: string;
}) {
  const [mode, setMode] = useState<ImportMode>("file");
  const [fileName, setFileName] = useState("");
  const [fileText, setFileText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tableName, setTableName] = useState("");
  const [replace, setReplace] = useState(false);
  const [status, setStatus] = useState("");

  const sourceLabel = useMemo(() => {
    if (mode === "url") return sourceUrl || "Remote CSV";
    return fileName || "Local CSV";
  }, [fileName, mode, sourceUrl]);

  async function submit() {
    setStatus("");
    if (!connectionId) {
      setStatus("Choose a connection first.");
      return;
    }
    if (mode === "file" && !fileText) {
      setStatus("Select a CSV file.");
      return;
    }
    if (mode === "url" && !sourceUrl.trim()) {
      setStatus("Enter a CSV URL.");
      return;
    }

    await onImport({
      connection_id: connectionId,
      csv_text: mode === "file" ? fileText : undefined,
      source_url: mode === "url" ? sourceUrl.trim() : undefined,
      file_name: fileName,
      table_name: tableName.trim(),
      replace
    });

    setStatus("Imported into the selected database.");
    if (mode === "file") {
      setFileText("");
      setFileName("");
    } else {
      setSourceUrl("");
    }
    setTableName("");
  }

  return (
    <section className="import-panel stack">
      <div className="panel-heading">
        <div>
          <h2 className="section-title">Load Data</h2>
          <p className="muted">Bring a CSV into the connected database from a file or URL.</p>
        </div>
      </div>

      <div className="mode-tabs">
        <button type="button" className={mode === "file" ? "tab active" : "tab"} onClick={() => setMode("file")}>
          CSV file
        </button>
        <button type="button" className={mode === "url" ? "tab active" : "tab"} onClick={() => setMode("url")}>
          CSV URL
        </button>
      </div>

      <div className="import-source">
        {mode === "file" ? (
          <>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                setFileName(file.name);
                if (!tableName.trim()) {
                  setTableName(deriveTableName(file.name));
                }
                setFileText(await fileToText(file));
              }}
            />
            <div className="muted small">Loaded file: {fileName || "none"}</div>
          </>
        ) : (
          <input
            value={sourceUrl}
            onChange={(event) => {
              const nextUrl = event.target.value;
              setSourceUrl(nextUrl);
              if (!tableName.trim()) {
                setTableName(deriveTableName(nextUrl));
              }
            }}
            placeholder="https://example.com/data.csv"
          />
        )}
      </div>

      <div className="import-grid">
        <input value={tableName} onChange={(event) => setTableName(event.target.value)} placeholder="Table name" />
        <label className="check-row">
          <input type="checkbox" checked={replace} onChange={(event) => setReplace(event.target.checked)} />
          <span>Replace existing table</span>
        </label>
      </div>

      <div className="toolbar">
        <button className="primary" type="button" onClick={submit} disabled={busy || !connectionId}>
          {busyAction === "import" ? "Importing..." : "Import CSV"}
        </button>
      </div>

      <div className="import-footer">
        <span className="muted small">Source: {sourceLabel}</span>
        {status ? <span className="inline-note success">{status}</span> : null}
      </div>
    </section>
  );
}

function fileToText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file."));
    reader.readAsText(file);
  });
}

function deriveTableName(value: string) {
  const stem = value.split("/").pop()?.split("?")[0]?.split("#")[0] ?? "";
  const withoutExtension = stem.replace(/\.csv$/i, "");
  const normalized = withoutExtension
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized ? `imported_${normalized}` : "imported_dataset";
}
