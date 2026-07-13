"use client";

import { ExecuteQueryResponse } from "../lib/types";

export function QueryResultTable({ result }: { result: ExecuteQueryResponse | null }) {
  if (!result) {
    return <p className="muted">No result yet.</p>;
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <strong>Results</strong>
        <span className="pill">{result.row_count} rows</span>
        <span className="muted">{result.execution_time_ms} ms</span>
        <span className="muted">{result.visualization_suggestion}</span>
      </div>
      <table className="result-table">
        <thead>
          <tr>
            {result.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.slice(0, 100).map((row, index) => (
            <tr key={index}>
              {result.columns.map((column) => (
                <td key={column}>{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
