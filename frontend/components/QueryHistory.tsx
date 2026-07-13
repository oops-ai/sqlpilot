"use client";

import { QueryHistoryEntry } from "../lib/types";

export function QueryHistory({ history, onSelect }: { history: QueryHistoryEntry[]; onSelect: (sql: string) => void }) {
  return (
    <section>
      <h2 className="section-title">History</h2>
      {history.length === 0 ? (
        <p className="muted">No queries yet.</p>
      ) : (
        history.map((entry) => (
          <button className="history-item" type="button" key={entry.id} onClick={() => onSelect(entry.generated_sql)}>
            <strong>{entry.user_request || "SQL query"}</strong>
            <div className="muted">{entry.safety_level}</div>
          </button>
        ))
      )}
    </section>
  );
}
