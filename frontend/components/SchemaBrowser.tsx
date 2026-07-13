"use client";

import { DatabaseSchema } from "../lib/types";

export function SchemaBrowser({ schema }: { schema: DatabaseSchema | null }) {
  const tables = schema ? Object.values(schema.tables) : [];

  return (
    <section>
      <h2 className="section-title">Schema</h2>
      {tables.length === 0 ? (
        <p className="muted">No schema loaded.</p>
      ) : (
        tables.map((table) => (
          <div className="schema-table" key={table.name}>
            <strong>{table.name}</strong>
            <ul className="schema-columns">
              {table.columns.map((column) => (
                <li key={column.name}>
                  {column.name} · {column.data_type}
                  {column.sensitive ? " · sensitive" : ""}
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
